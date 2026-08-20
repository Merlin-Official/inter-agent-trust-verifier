"""
Credential revocation endpoints.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import Agent, AgentStatus, RevocationRecord
from app.core.revocation import revocation_manager
from app.api.schemas import RevokeAgentRequest, RevocationStatusResponse

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/agents", tags=["Revocation"])


@router.post(
    "/{agent_id}/revoke",
    status_code=status.HTTP_200_OK,
    summary="Revoke an agent's credentials",
)
async def revoke_agent(
    agent_id: str,
    request: RevokeAgentRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke an agent's credentials.

    After revocation:
    - All subsequent instructions from this agent are REJECTED
    - The agent's delegation tokens are invalidated
    - Rejection happens within ONE verification cycle
    """
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    if agent.status == AgentStatus.REVOKED:
        raise HTTPException(status_code=400, detail=f"Agent '{agent.name}' is already revoked")

    await revocation_manager.revoke_agent(
        db=db,
        agent_id=agent_id,
        reason=request.reason,
        revoked_by=request.revoked_by,
    )

    logger.warning(
        "agent_revoked",
        agent_id=agent_id,
        agent_name=agent.name,
        reason=request.reason,
        revoked_by=request.revoked_by,
    )

    return {
        "status": "revoked",
        "agent_id": agent_id,
        "agent_name": agent.name,
        "reason": request.reason,
        "message": f"Agent '{agent.name}' credentials have been revoked. All future instructions will be rejected.",
    }


@router.post(
    "/{agent_id}/suspend",
    status_code=status.HTTP_200_OK,
    summary="Suspend an agent",
)
async def suspend_agent(
    agent_id: str,
    request: RevokeAgentRequest,
    db: AsyncSession = Depends(get_db),
):
    """Suspend an agent (can be reactivated later)."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    await revocation_manager.suspend_agent(
        db=db,
        agent_id=agent_id,
        reason=request.reason,
        suspended_by=request.revoked_by,
    )

    logger.warning("agent_suspended", agent_id=agent_id, agent_name=agent.name)

    return {
        "status": "suspended",
        "agent_id": agent_id,
        "agent_name": agent.name,
        "message": f"Agent '{agent.name}' has been suspended.",
    }


@router.post(
    "/{agent_id}/reactivate",
    status_code=status.HTTP_200_OK,
    summary="Reactivate an agent",
)
async def reactivate_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Reactivate a suspended or revoked agent."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    await revocation_manager.reactivate_agent(db=db, agent_id=agent_id)
    logger.info("agent_reactivated", agent_id=agent_id, agent_name=agent.name)

    return {
        "status": "active",
        "agent_id": agent_id,
        "agent_name": agent.name,
        "message": f"Agent '{agent.name}' has been reactivated.",
    }


@router.get(
    "/{agent_id}/revocation-status",
    response_model=RevocationStatusResponse,
    summary="Get revocation status",
)
async def get_revocation_status(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the revocation status and history for an agent."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    # Get revocation history
    result = await db.execute(
        select(RevocationRecord)
        .where(RevocationRecord.agent_id == agent_id)
        .order_by(RevocationRecord.revoked_at.desc())
    )
    records = result.scalars().all()

    return RevocationStatusResponse(
        agent_id=agent.id,
        agent_name=agent.name,
        status=agent.status.value,
        revocation_history=[
            {
                "reason": r.reason,
                "revoked_by": r.revoked_by,
                "revoked_at": r.revoked_at.isoformat() if r.revoked_at else "",
            }
            for r in records
        ],
    )
