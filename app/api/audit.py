"""
Audit trail and reputation endpoints.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import AuditLog, VerificationOutcome, Agent, ReputationScore
from app.core.reputation import reputation_tracker
from app.api.schemas import (
    AuditLogResponse,
    ReputationResponse,
    DashboardStatsResponse,
)

router = APIRouter(prefix="/api/v1", tags=["Audit & Reputation"])


# ─── Audit Trail ──────────────────────────────────────────────────────

@router.get(
    "/audit-logs",
    response_model=list[AuditLogResponse],
    summary="Query audit trail",
)
async def get_audit_logs(
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    outcome: str = Query(default=None, description="Filter: ACCEPTED or REJECTED"),
    sender_id: str = Query(default=None),
    receiver_id: str = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Query the audit trail with optional filters.
    Every verification outcome is logged here.
    """
    query = select(AuditLog).order_by(desc(AuditLog.timestamp))

    if outcome:
        query = query.where(AuditLog.outcome == outcome)
    if sender_id:
        query = query.where(AuditLog.sender_id == sender_id)
    if receiver_id:
        query = query.where(AuditLog.receiver_id == receiver_id)

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        AuditLogResponse(
            id=log.id,
            instruction_id=log.instruction_id,
            sender_id=log.sender_id,
            sender_name=log.sender_name,
            receiver_id=log.receiver_id,
            receiver_name=log.receiver_name,
            action=log.action,
            outcome=log.outcome.value if hasattr(log.outcome, 'value') else log.outcome,
            reason=log.reason,
            checks_passed=log.checks_passed,
            checks_failed=log.checks_failed,
            timestamp=log.timestamp,
        )
        for log in logs
    ]


# ─── Reputation ──────────────────────────────────────────────────────

@router.get(
    "/reputation/{agent_id}",
    response_model=ReputationResponse,
    summary="Get agent's trust reputation score",
)
async def get_reputation(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the trust reputation score for a specific agent."""
    result = await db.execute(
        select(ReputationScore).where(ReputationScore.agent_id == agent_id)
    )
    rep = result.scalar_one_or_none()
    if not rep:
        return ReputationResponse(
            agent_id=agent_id,
            score=100.0,
            total_accepted=0,
            total_rejected=0,
            needs_scrutiny=False,
            updated_at=None,
        )

    # Get agent name
    agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = agent_result.scalar_one_or_none()

    return ReputationResponse(
        agent_id=rep.agent_id,
        agent_name=agent.name if agent else None,
        score=rep.score,
        total_accepted=rep.total_accepted,
        total_rejected=rep.total_rejected,
        needs_scrutiny=reputation_tracker.needs_scrutiny(rep.score),
        updated_at=rep.updated_at,
    )


@router.get(
    "/reputation",
    response_model=list[ReputationResponse],
    summary="Get reputation leaderboard",
)
async def get_reputation_leaderboard(
    db: AsyncSession = Depends(get_db),
):
    """Get all agent reputation scores, ranked by score."""
    scores = await reputation_tracker.get_all_scores(db)
    results = []
    for rep in scores:
        agent_result = await db.execute(select(Agent).where(Agent.id == rep.agent_id))
        agent = agent_result.scalar_one_or_none()
        results.append(
            ReputationResponse(
                agent_id=rep.agent_id,
                agent_name=agent.name if agent else None,
                score=rep.score,
                total_accepted=rep.total_accepted,
                total_rejected=rep.total_rejected,
                needs_scrutiny=reputation_tracker.needs_scrutiny(rep.score),
                updated_at=rep.updated_at,
            )
        )
    return results


# ─── Dashboard Stats ─────────────────────────────────────────────────

@router.get(
    "/stats",
    response_model=DashboardStatsResponse,
    summary="Get dashboard statistics",
)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get overall system statistics for the dashboard."""
    from app.models.models import AgentStatus

    # Agent counts
    total = await db.execute(select(func.count(Agent.id)))
    total_agents = total.scalar() or 0

    active = await db.execute(
        select(func.count(Agent.id)).where(Agent.status == AgentStatus.ACTIVE)
    )
    active_agents = active.scalar() or 0

    revoked = await db.execute(
        select(func.count(Agent.id)).where(Agent.status == AgentStatus.REVOKED)
    )
    revoked_agents = revoked.scalar() or 0

    suspended = await db.execute(
        select(func.count(Agent.id)).where(Agent.status == AgentStatus.SUSPENDED)
    )
    suspended_agents = suspended.scalar() or 0

    # Instruction counts
    total_instr = await db.execute(select(func.count(AuditLog.id)))
    total_instructions = total_instr.scalar() or 0

    accepted = await db.execute(
        select(func.count(AuditLog.id)).where(
            AuditLog.outcome == VerificationOutcome.ACCEPTED
        )
    )
    total_accepted = accepted.scalar() or 0

    rejected = await db.execute(
        select(func.count(AuditLog.id)).where(
            AuditLog.outcome == VerificationOutcome.REJECTED
        )
    )
    total_rejected = rejected.scalar() or 0

    acceptance_rate = (
        (total_accepted / total_instructions * 100) if total_instructions > 0 else 0.0
    )

    return DashboardStatsResponse(
        total_agents=total_agents,
        active_agents=active_agents,
        revoked_agents=revoked_agents,
        suspended_agents=suspended_agents,
        total_instructions=total_instructions,
        total_accepted=total_accepted,
        total_rejected=total_rejected,
        acceptance_rate=round(acceptance_rate, 1),
    )
