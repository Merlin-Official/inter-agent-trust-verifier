"""
Credential Revocation System.

Manages agent status transitions: ACTIVE → SUSPENDED → REVOKED
and maintains an in-memory + DB-backed Certificate Revocation List (CRL).

Every verification queries this before accepting instructions.
"""

from datetime import datetime, timezone
from typing import Optional, Set
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Agent, AgentStatus, RevocationRecord, DelegationToken


class RevocationManager:
    """
    Manages agent and delegation token revocations.

    Maintains an in-memory set for O(1) lookups,
    backed by PostgreSQL for persistence.
    """

    def __init__(self):
        self._revoked_agents: Set[str] = set()
        self._suspended_agents: Set[str] = set()

    async def load_from_db(self, db: AsyncSession):
        """Load revocation state from database on startup."""
        result = await db.execute(
            select(Agent).where(Agent.status == AgentStatus.REVOKED)
        )
        for agent in result.scalars().all():
            self._revoked_agents.add(agent.id)

        result = await db.execute(
            select(Agent).where(Agent.status == AgentStatus.SUSPENDED)
        )
        for agent in result.scalars().all():
            self._suspended_agents.add(agent.id)

    async def revoke_agent(
        self,
        db: AsyncSession,
        agent_id: str,
        reason: str,
        revoked_by: str = "system",
    ) -> bool:
        """
        Revoke an agent's credentials.
        Updates both in-memory CRL and database.
        """
        # Update agent status
        await db.execute(
            update(Agent)
            .where(Agent.id == agent_id)
            .values(
                status=AgentStatus.REVOKED,
                updated_at=datetime.now(timezone.utc),
            )
        )

        # Also revoke all delegation tokens from this agent
        await db.execute(
            update(DelegationToken)
            .where(DelegationToken.subject_id == agent_id)
            .values(is_revoked=True)
        )

        # Create revocation record
        record = RevocationRecord(
            agent_id=agent_id,
            reason=reason,
            revoked_by=revoked_by,
        )
        db.add(record)
        await db.flush()

        # Update in-memory CRL
        self._revoked_agents.add(agent_id)
        self._suspended_agents.discard(agent_id)

        return True

    async def suspend_agent(
        self,
        db: AsyncSession,
        agent_id: str,
        reason: str,
        suspended_by: str = "system",
    ) -> bool:
        """Suspend an agent (can be reactivated)."""
        await db.execute(
            update(Agent)
            .where(Agent.id == agent_id)
            .values(
                status=AgentStatus.SUSPENDED,
                updated_at=datetime.now(timezone.utc),
            )
        )

        record = RevocationRecord(
            agent_id=agent_id,
            reason=f"SUSPENDED: {reason}",
            revoked_by=suspended_by,
        )
        db.add(record)
        await db.flush()

        self._suspended_agents.add(agent_id)
        return True

    async def reactivate_agent(
        self,
        db: AsyncSession,
        agent_id: str,
    ) -> bool:
        """Reactivate a suspended or revoked agent."""
        await db.execute(
            update(Agent)
            .where(Agent.id == agent_id)
            .values(
                status=AgentStatus.ACTIVE,
                updated_at=datetime.now(timezone.utc),
            )
        )

        self._revoked_agents.discard(agent_id)
        self._suspended_agents.discard(agent_id)
        return True

    def is_revoked(self, agent_id: str) -> bool:
        """O(1) check if an agent is revoked."""
        return agent_id in self._revoked_agents

    def is_suspended(self, agent_id: str) -> bool:
        """O(1) check if an agent is suspended."""
        return agent_id in self._suspended_agents

    def is_active(self, agent_id: str) -> bool:
        """Check if an agent is active (not revoked or suspended)."""
        return not self.is_revoked(agent_id) and not self.is_suspended(agent_id)


# Global singleton
revocation_manager = RevocationManager()
