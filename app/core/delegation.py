"""
Delegation token creation and validation.

Delegation tokens define what Agent A is authorized to instruct Agent B to do.
They contain allowed actions, target restrictions, and an expiration date.
The token is signed by the issuer for integrity.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field

from app.core.crypto import canonical_json, sign_message, verify_signature


class DelegationTokenData(BaseModel):
    """Structure of a delegation token."""
    token_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    issuer_id: str
    subject_id: str
    allowed_actions: List[str]
    allowed_targets: Optional[List[str]] = None
    expires_at: str  # ISO format datetime
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SignedDelegationToken(BaseModel):
    """A delegation token with its issuer's signature."""
    token_id: str
    issuer_id: str
    subject_id: str
    allowed_actions: List[str]
    allowed_targets: Optional[List[str]] = None
    expires_at: str
    created_at: str
    signature: str


def create_delegation_token(
    issuer_private_key_pem: str,
    issuer_id: str,
    subject_id: str,
    allowed_actions: List[str],
    expires_at: str,
    allowed_targets: Optional[List[str]] = None,
) -> SignedDelegationToken:
    """
    Create and sign a delegation token.

    Args:
        issuer_private_key_pem: Issuer's Ed25519 private key.
        issuer_id: ID of the issuing agent (or admin).
        subject_id: ID of the agent being delegated authority.
        allowed_actions: List of actions the subject can instruct.
        expires_at: ISO format expiration datetime.
        allowed_targets: Optional specific target agents.

    Returns:
        A signed delegation token.
    """
    token = DelegationTokenData(
        issuer_id=issuer_id,
        subject_id=subject_id,
        allowed_actions=allowed_actions,
        allowed_targets=allowed_targets,
        expires_at=expires_at,
    )

    signing_data = _get_token_signing_data(token)
    signature = sign_message(issuer_private_key_pem, signing_data)

    return SignedDelegationToken(
        token_id=token.token_id,
        issuer_id=token.issuer_id,
        subject_id=token.subject_id,
        allowed_actions=token.allowed_actions,
        allowed_targets=token.allowed_targets,
        expires_at=token.expires_at,
        created_at=token.created_at,
        signature=signature,
    )


def verify_delegation_token_signature(
    issuer_public_key_pem: str,
    token: SignedDelegationToken,
) -> bool:
    """
    Verify the signature of a delegation token.

    Args:
        issuer_public_key_pem: Issuer's public key.
        token: The signed delegation token.

    Returns:
        True if the signature is valid.
    """
    token_data = DelegationTokenData(
        token_id=token.token_id,
        issuer_id=token.issuer_id,
        subject_id=token.subject_id,
        allowed_actions=token.allowed_actions,
        allowed_targets=token.allowed_targets,
        expires_at=token.expires_at,
        created_at=token.created_at,
    )
    signing_data = _get_token_signing_data(token_data)
    return verify_signature(issuer_public_key_pem, signing_data, token.signature)


def is_token_expired(expires_at: str) -> bool:
    """Check if a delegation token has expired."""
    try:
        expiry = datetime.fromisoformat(expires_at)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > expiry
    except (ValueError, TypeError):
        return True  # Invalid date = expired


def is_action_in_scope(action: str, allowed_actions: List[str]) -> bool:
    """Check if an action is within the delegation's allowed actions."""
    # Support wildcard
    if "*" in allowed_actions:
        return True
    return action in allowed_actions


def _get_token_signing_data(token: DelegationTokenData) -> bytes:
    """Get canonical bytes for signing a delegation token."""
    signing_dict = {
        "token_id": token.token_id,
        "issuer_id": token.issuer_id,
        "subject_id": token.subject_id,
        "allowed_actions": sorted(token.allowed_actions),
        "expires_at": token.expires_at,
        "created_at": token.created_at,
    }
    if token.allowed_targets:
        signing_dict["allowed_targets"] = sorted(token.allowed_targets)
    return canonical_json(signing_dict)
