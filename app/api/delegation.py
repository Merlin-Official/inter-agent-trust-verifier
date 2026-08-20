"""
Delegation token endpoints.
"""

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import Agent, DelegationToken as DelegationTokenModel
from app.core.delegation import create_delegation_token
from app.api.schemas import DelegationCreateRequest, DelegationResponse

router = APIRouter(prefix="/api/v1/delegations", tags=["Delegations"])


@router.post(
    "",
    response_model=DelegationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a delegation token",
)
async def create_delegation(
    request: DelegationCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Issue a delegation token granting one agent permission
    to instruct another for specific actions.
    """
    # Verify issuer exists
    issuer = await db.execute(
        select(Agent).where(Agent.id == request.issuer_id)
    )
    issuer = issuer.scalar_one_or_none()
    if not issuer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issuer agent '{request.issuer_id}' not found",
        )

    # Verify subject exists
    subject = await db.execute(
        select(Agent).where(Agent.id == request.subject_id)
    )
    subject = subject.scalar_one_or_none()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject agent '{request.subject_id}' not found",
        )

    # Calculate expiration
    expires_at = datetime.now(timezone.utc) + timedelta(hours=request.expires_in_hours)

    # Create signed delegation token
    signed_token = create_delegation_token(
        issuer_private_key_pem=request.issuer_private_key,
        issuer_id=request.issuer_id,
        subject_id=request.subject_id,
        allowed_actions=request.allowed_actions,
        expires_at=expires_at.isoformat(),
        allowed_targets=request.allowed_targets,
    )

    # Persist to database
    token_record = DelegationTokenModel(
        id=signed_token.token_id,
        issuer_id=signed_token.issuer_id,
        subject_id=signed_token.subject_id,
        allowed_actions=signed_token.allowed_actions,
        allowed_targets=signed_token.allowed_targets,
        expires_at=signed_token.expires_at,
        signature=signed_token.signature,
        created_at=signed_token.created_at,
    )
    db.add(token_record)
    await db.flush()

    return DelegationResponse(
        token_id=signed_token.token_id,
        issuer_id=signed_token.issuer_id,
        subject_id=signed_token.subject_id,
        allowed_actions=signed_token.allowed_actions,
        allowed_targets=signed_token.allowed_targets,
        expires_at=signed_token.expires_at,
        is_revoked=False,
        signature=signed_token.signature,
        created_at=token_record.created_at,
    )


@router.get(
    "/{token_id}",
    response_model=DelegationResponse,
    summary="Get delegation token details",
)
async def get_delegation(
    token_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get details for a specific delegation token."""
    result = await db.execute(
        select(DelegationTokenModel).where(DelegationTokenModel.id == token_id)
    )
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Delegation token '{token_id}' not found",
        )
    return DelegationResponse(
        token_id=token.id,
        issuer_id=token.issuer_id,
        subject_id=token.subject_id,
        allowed_actions=token.allowed_actions,
        allowed_targets=token.allowed_targets,
        expires_at=token.expires_at,
        is_revoked=token.is_revoked,
        signature=token.signature or "",
        created_at=token.created_at,
    )


@router.get(
    "/agent/{agent_id}",
    response_model=list[DelegationResponse],
    summary="List delegation tokens for an agent",
)
async def list_agent_delegations(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    """List all delegation tokens where the agent is either issuer or subject."""
    result = await db.execute(
        select(DelegationTokenModel).where(
            (DelegationTokenModel.issuer_id == agent_id)
            | (DelegationTokenModel.subject_id == agent_id)
        ).order_by(DelegationTokenModel.created_at.desc())
    )
    tokens = result.scalars().all()
    return [
        DelegationResponse(
            token_id=t.id,
            issuer_id=t.issuer_id,
            subject_id=t.subject_id,
            allowed_actions=t.allowed_actions,
            allowed_targets=t.allowed_targets,
            expires_at=t.expires_at,
            is_revoked=t.is_revoked,
            signature=t.signature or "",
            created_at=t.created_at,
        )
        for t in tokens
    ]
