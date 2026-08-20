"""
Instruction signing, verification, and execution endpoints.

The core flow:
  Instruction → Trust Verifier → ACCEPT/REJECT → (Execute if accepted)
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import (
    Agent,
    DelegationToken as DelegationTokenModel,
    Instruction as InstructionModel,
    AuditLog,
    VerificationOutcome,
)
from app.core.crypto import verify_signature
from app.core.instruction import (
    create_signed_instruction,
    SignedInstruction,
    get_instruction_signing_bytes,
)
from app.core.delegation import SignedDelegationToken
from app.core.verifier import TrustVerifier, AgentInfo
from app.core.revocation import revocation_manager
from app.core.reputation import reputation_tracker
from app.core.llm_policy import llm_analyzer
from app.api.schemas import (
    InstructionSignRequest,
    SignedInstructionResponse,
    InstructionVerifyRequest,
    VerificationResponse,
    VerificationCheckResponse,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/instructions", tags=["Instructions"])
trust_verifier = TrustVerifier()


@router.post(
    "/sign",
    response_model=SignedInstructionResponse,
    summary="Sign an instruction",
)
async def sign_instruction(
    request: InstructionSignRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create and sign an instruction with the sender's private key.
    Returns the signed instruction ready for verification.
    """
    # Verify sender exists
    result = await db.execute(select(Agent).where(Agent.id == request.sender_id))
    sender = result.scalar_one_or_none()
    if not sender:
        raise HTTPException(status_code=404, detail=f"Sender agent '{request.sender_id}' not found")

    # Verify receiver exists
    result = await db.execute(select(Agent).where(Agent.id == request.receiver_id))
    receiver = result.scalar_one_or_none()
    if not receiver:
        raise HTTPException(status_code=404, detail=f"Receiver agent '{request.receiver_id}' not found")

    # Verify delegation token exists
    result = await db.execute(
        select(DelegationTokenModel).where(DelegationTokenModel.id == request.delegation_token_id)
    )
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(status_code=404, detail=f"Delegation token '{request.delegation_token_id}' not found")

    # Create signed instruction
    try:
        signed = create_signed_instruction(
            private_key_pem=request.sender_private_key,
            sender_id=request.sender_id,
            receiver_id=request.receiver_id,
            action=request.action,
            delegation_token_id=request.delegation_token_id,
            payload=request.payload,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to sign instruction: {str(e)}")

    logger.info(
        "instruction_signed",
        instruction_id=signed.instruction_id,
        sender=sender.name,
        receiver=receiver.name,
        action=request.action,
    )

    return SignedInstructionResponse(
        instruction_id=signed.instruction_id,
        sender_id=signed.sender_id,
        receiver_id=signed.receiver_id,
        action=signed.action,
        payload=signed.payload,
        delegation_token_id=signed.delegation_token_id,
        timestamp=signed.timestamp,
        signature=signed.signature,
    )


@router.post(
    "/verify",
    response_model=VerificationResponse,
    summary="Verify a signed instruction",
)
async def verify_instruction(
    request: InstructionVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify a signed instruction through the deterministic trust engine.
    This is a verification-only endpoint (does not execute).
    """
    return await _run_verification(request, db, execute=False)


@router.post(
    "/execute",
    response_model=VerificationResponse,
    summary="Verify and execute a signed instruction",
)
async def verify_and_execute(
    request: InstructionVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify a signed instruction and execute it if accepted.

    Flow: Instruction → Trust Verifier → ACCEPT/REJECT
    Verification ALWAYS happens before execution.
    """
    return await _run_verification(request, db, execute=True)


async def _run_verification(
    request: InstructionVerifyRequest,
    db: AsyncSession,
    execute: bool,
) -> VerificationResponse:
    """Core verification logic shared by verify and execute endpoints."""

    # ─── Load sender agent ─────────────────────────────────────
    result = await db.execute(select(Agent).where(Agent.id == request.sender_id))
    sender = result.scalar_one_or_none()
    if not sender:
        raise HTTPException(status_code=404, detail=f"Sender agent '{request.sender_id}' not found")

    # ─── Load receiver agent ───────────────────────────────────
    result = await db.execute(select(Agent).where(Agent.id == request.receiver_id))
    receiver = result.scalar_one_or_none()
    if not receiver:
        raise HTTPException(status_code=404, detail=f"Receiver agent '{request.receiver_id}' not found")

    # ─── Load delegation token ─────────────────────────────────
    result = await db.execute(
        select(DelegationTokenModel).where(
            DelegationTokenModel.id == request.delegation_token_id
        )
    )
    token_record = result.scalar_one_or_none()
    if not token_record:
        raise HTTPException(
            status_code=404,
            detail=f"Delegation token '{request.delegation_token_id}' not found",
        )

    # Build domain objects for the verifier
    sender_info = AgentInfo(
        id=sender.id,
        name=sender.name,
        public_key=sender.public_key,
        status=sender.status.value,
        policy_scope=sender.policy_scope or [],
    )
    receiver_info = AgentInfo(
        id=receiver.id,
        name=receiver.name,
        public_key=receiver.public_key,
        status=receiver.status.value,
        policy_scope=receiver.policy_scope or [],
    )

    # Get issuer's public key for delegation verification
    result = await db.execute(
        select(Agent).where(Agent.id == token_record.issuer_id)
    )
    issuer = result.scalar_one_or_none()
    issuer_public_key = issuer.public_key if issuer else ""

    signed_delegation = SignedDelegationToken(
        token_id=token_record.id,
        issuer_id=token_record.issuer_id,
        subject_id=token_record.subject_id,
        allowed_actions=token_record.allowed_actions or [],
        allowed_targets=token_record.allowed_targets,
        expires_at=token_record.expires_at,
        created_at=token_record.created_at,
        signature=token_record.signature or "",
    )

    signed_instruction = SignedInstruction(
        instruction_id=request.instruction_id,
        sender_id=request.sender_id,
        receiver_id=request.receiver_id,
        action=request.action,
        payload=request.payload,
        delegation_token_id=request.delegation_token_id,
        timestamp=request.timestamp,
        signature=request.signature,
    )

    # Get reputation score
    rep_score = await reputation_tracker.get_score(db, sender.id)

    # ─── Run the deterministic trust verifier ──────────────────
    verification = trust_verifier.verify(
        instruction=signed_instruction,
        sender=sender_info,
        receiver=receiver_info,
        delegation_token=signed_delegation,
        issuer_public_key=issuer_public_key,
        is_delegation_revoked=token_record.is_revoked,
        sender_reputation_score=rep_score,
    )

    # ─── Persist the instruction ───────────────────────────────
    instr_record = InstructionModel(
        id=request.instruction_id,
        sender_id=request.sender_id,
        receiver_id=request.receiver_id,
        action=request.action,
        payload=request.payload,
        delegation_token_id=request.delegation_token_id,
        signature=request.signature,
        verification_outcome=(
            VerificationOutcome.ACCEPTED if verification.accepted
            else VerificationOutcome.REJECTED
        ),
    )
    db.add(instr_record)

    # ─── Update reputation ─────────────────────────────────────
    if verification.accepted:
        await reputation_tracker.record_accepted(db, sender.id)
    else:
        await reputation_tracker.record_rejected(db, sender.id)

    # ─── Create audit log ──────────────────────────────────────
    audit = AuditLog(
        instruction_id=request.instruction_id,
        sender_id=sender.id,
        sender_name=sender.name,
        receiver_id=receiver.id,
        receiver_name=receiver.name,
        action=request.action,
        outcome=(
            VerificationOutcome.ACCEPTED if verification.accepted
            else VerificationOutcome.REJECTED
        ),
        reason=verification.rejection_reason,
        checks_passed=verification.checks_passed,
        checks_failed=verification.checks_failed,
    )
    db.add(audit)

    # ─── LLM explanation (non-blocking, for audit) ─────────────
    llm_explanation = None
    try:
        llm_explanation = await llm_analyzer.explain_verification(
            action=request.action,
            sender_name=sender.name,
            receiver_name=receiver.name,
            outcome="ACCEPTED" if verification.accepted else "REJECTED",
            reason=verification.rejection_reason,
            checks_passed=verification.checks_passed,
            checks_failed=verification.checks_failed,
        )
    except Exception:
        pass  # Never let LLM failure block verification

    # ─── Log result ────────────────────────────────────────────
    log_method = logger.info if verification.accepted else logger.warning
    log_method(
        "instruction_verified",
        instruction_id=request.instruction_id,
        sender=sender.name,
        receiver=receiver.name,
        action=request.action,
        outcome="ACCEPTED" if verification.accepted else "REJECTED",
        reason=verification.rejection_reason,
        execute=execute,
    )

    if verification.accepted and execute:
        logger.info(
            "instruction_executed",
            instruction_id=request.instruction_id,
            action=request.action,
            sender=sender.name,
            receiver=receiver.name,
        )

    return VerificationResponse(
        accepted=verification.accepted,
        instruction_id=verification.instruction_id,
        checks=[
            VerificationCheckResponse(
                name=c.name,
                passed=c.passed,
                detail=c.detail,
            )
            for c in verification.checks
        ],
        rejection_reason=verification.rejection_reason,
        llm_explanation=llm_explanation,
        timestamp=verification.timestamp,
    )
