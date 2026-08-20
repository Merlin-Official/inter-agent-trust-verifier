"""
Deterministic Trust Verification Engine.

This is the CORE of the Inter-Agent Trust Verifier system.
It performs a chain of deterministic security checks before
accepting or rejecting an instruction.

Check chain:
1. Signature Verification — Ed25519 signature is valid
2. Sender Agent Status — Sender is not revoked/suspended
3. Delegation Token Validation — Token signature is valid, not revoked
4. Delegation Expiration — Token has not expired
5. Delegation Scope — Requested action is in allowed_actions
6. Receiver Policy — Action is within receiver's accepted policy_scope
7. Reputation Check (optional) — Sender's trust score above threshold

The LLM is NOT used for security decisions. It provides explanations only.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List
from dataclasses import dataclass, field
from pydantic import BaseModel

from app.core.crypto import verify_signature
from app.core.instruction import SignedInstruction, get_instruction_signing_bytes
from app.core.delegation import (
    SignedDelegationToken,
    verify_delegation_token_signature,
    is_token_expired,
    is_action_in_scope,
)


@dataclass
class VerificationCheck:
    """Result of a single verification check."""
    name: str
    passed: bool
    detail: str


@dataclass
class VerificationResult:
    """Complete result of trust verification."""
    accepted: bool
    instruction_id: str
    checks: List[VerificationCheck] = field(default_factory=list)
    rejection_reason: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def checks_passed(self) -> List[str]:
        return [c.name for c in self.checks if c.passed]

    @property
    def checks_failed(self) -> List[str]:
        return [c.name for c in self.checks if not c.passed]


class AgentInfo(BaseModel):
    """Minimal agent info needed for verification."""
    id: str
    name: str
    public_key: str
    status: str  # ACTIVE, SUSPENDED, REVOKED
    policy_scope: List[str]


class TrustVerifier:
    """
    Deterministic trust verification engine.

    Performs a strict chain of checks. If any check fails,
    the instruction is REJECTED immediately with the reason.
    """

    def verify(
        self,
        instruction: SignedInstruction,
        sender: AgentInfo,
        receiver: AgentInfo,
        delegation_token: SignedDelegationToken,
        issuer_public_key: str,
        is_delegation_revoked: bool = False,
        sender_reputation_score: Optional[float] = None,
        reputation_threshold: float = 50.0,
    ) -> VerificationResult:
        """
        Run all verification checks on an instruction.

        Args:
            instruction: The signed instruction to verify.
            sender: Agent info for the sender.
            receiver: Agent info for the receiver.
            delegation_token: The delegation token authorizing this instruction.
            issuer_public_key: Public key of the delegation token issuer.
            is_delegation_revoked: Whether the delegation token has been revoked.
            sender_reputation_score: Current reputation score (None to skip).
            reputation_threshold: Score below which heightened scrutiny applies.

        Returns:
            VerificationResult with accepted/rejected and all check details.
        """
        checks: List[VerificationCheck] = []
        result_id = instruction.instruction_id

        # ─── Check 1: Signature Verification ───────────────────────
        signing_bytes = get_instruction_signing_bytes(instruction)
        sig_valid = verify_signature(
            sender.public_key, signing_bytes, instruction.signature
        )
        checks.append(VerificationCheck(
            name="signature_verification",
            passed=sig_valid,
            detail="Ed25519 signature is valid" if sig_valid
            else "Ed25519 signature verification FAILED — possible tampering or MITM",
        ))
        if not sig_valid:
            return VerificationResult(
                accepted=False,
                instruction_id=result_id,
                checks=checks,
                rejection_reason="Invalid signature — instruction may have been tampered with",
            )

        # ─── Check 2: Sender Agent Status ──────────────────────────
        sender_active = sender.status == "ACTIVE"
        checks.append(VerificationCheck(
            name="sender_status",
            passed=sender_active,
            detail=f"Sender agent status: {sender.status}",
        ))
        if not sender_active:
            return VerificationResult(
                accepted=False,
                instruction_id=result_id,
                checks=checks,
                rejection_reason=f"Sender agent credentials {sender.status.lower()} — instruction rejected",
            )

        # ─── Check 3: Delegation Token Signature ───────────────────
        token_sig_valid = verify_delegation_token_signature(
            issuer_public_key, delegation_token
        )
        checks.append(VerificationCheck(
            name="delegation_signature",
            passed=token_sig_valid,
            detail="Delegation token signature is valid" if token_sig_valid
            else "Delegation token signature verification FAILED",
        ))
        if not token_sig_valid:
            return VerificationResult(
                accepted=False,
                instruction_id=result_id,
                checks=checks,
                rejection_reason="Invalid delegation token signature",
            )

        # ─── Check 4: Delegation Token Revocation ──────────────────
        delegation_not_revoked = not is_delegation_revoked
        checks.append(VerificationCheck(
            name="delegation_revocation",
            passed=delegation_not_revoked,
            detail="Delegation token is active" if delegation_not_revoked
            else "Delegation token has been REVOKED",
        ))
        if not delegation_not_revoked:
            return VerificationResult(
                accepted=False,
                instruction_id=result_id,
                checks=checks,
                rejection_reason="Delegation token has been revoked",
            )

        # ─── Check 5: Delegation Expiration ────────────────────────
        expired = is_token_expired(delegation_token.expires_at)
        checks.append(VerificationCheck(
            name="delegation_expiration",
            passed=not expired,
            detail=f"Delegation token expires at {delegation_token.expires_at}"
            if not expired
            else f"Delegation token EXPIRED at {delegation_token.expires_at}",
        ))
        if expired:
            return VerificationResult(
                accepted=False,
                instruction_id=result_id,
                checks=checks,
                rejection_reason=f"Delegation token expired at {delegation_token.expires_at}",
            )

        # ─── Check 6: Delegation Scope ─────────────────────────────
        in_scope = is_action_in_scope(
            instruction.action, delegation_token.allowed_actions
        )
        checks.append(VerificationCheck(
            name="delegation_scope",
            passed=in_scope,
            detail=f"Action '{instruction.action}' is within delegation scope {delegation_token.allowed_actions}"
            if in_scope
            else f"Action '{instruction.action}' is NOT in delegation scope {delegation_token.allowed_actions}",
        ))
        if not in_scope:
            return VerificationResult(
                accepted=False,
                instruction_id=result_id,
                checks=checks,
                rejection_reason=f"Action '{instruction.action}' exceeds delegation scope — allowed: {delegation_token.allowed_actions}",
            )

        # ─── Check 7: Receiver Policy Scope ────────────────────────
        receiver_allows = (
            "*" in receiver.policy_scope
            or instruction.action in receiver.policy_scope
        )
        checks.append(VerificationCheck(
            name="receiver_policy",
            passed=receiver_allows,
            detail=f"Action '{instruction.action}' is within receiver's policy scope"
            if receiver_allows
            else f"Action '{instruction.action}' is NOT in receiver's policy scope {receiver.policy_scope}",
        ))
        if not receiver_allows:
            return VerificationResult(
                accepted=False,
                instruction_id=result_id,
                checks=checks,
                rejection_reason=f"Action '{instruction.action}' is outside receiver's policy scope",
            )

        # ─── Check 8: Reputation (Optional) ────────────────────────
        if sender_reputation_score is not None:
            rep_ok = sender_reputation_score >= reputation_threshold
            checks.append(VerificationCheck(
                name="reputation_check",
                passed=rep_ok,
                detail=f"Sender reputation score: {sender_reputation_score:.1f} (threshold: {reputation_threshold})"
                if rep_ok
                else f"Sender reputation score {sender_reputation_score:.1f} BELOW threshold {reputation_threshold} — heightened scrutiny triggered",
            ))
            if not rep_ok:
                return VerificationResult(
                    accepted=False,
                    instruction_id=result_id,
                    checks=checks,
                    rejection_reason=f"Sender reputation score ({sender_reputation_score:.1f}) below trust threshold ({reputation_threshold})",
                )

        # ─── All checks passed ─────────────────────────────────────
        return VerificationResult(
            accepted=True,
            instruction_id=result_id,
            checks=checks,
        )
