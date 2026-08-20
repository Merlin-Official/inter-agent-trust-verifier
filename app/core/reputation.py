"""
Trust Reputation Scoring System (Bonus Feature).

Tracks per-agent trust scores based on verification outcomes.
- Accepted instructions: +1 point
- Rejected instructions: -5 points
- Score below threshold triggers heightened scrutiny
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import ReputationScore
from app.config import get_settings


class ReputationTracker:
    """Manages agent reputation scores."""

    def __init__(self):
        settings = get_settings()
        self.initial_score = settings.REPUTATION_INITIAL_SCORE
        self.accept_bonus = settings.REPUTATION_ACCEPT_BONUS
        self.reject_penalty = settings.REPUTATION_REJECT_PENALTY
        self.scrutiny_threshold = settings.REPUTATION_SCRUTINY_THRESHOLD

    async def initialize_score(self, db: AsyncSession, agent_id: str):
        """Create initial reputation score for a new agent."""
        score = ReputationScore(
            agent_id=agent_id,
            score=self.initial_score,
            total_accepted=0,
            total_rejected=0,
        )
        db.add(score)
        await db.flush()

    async def record_accepted(self, db: AsyncSession, agent_id: str):
        """Record an accepted instruction — boost score."""
        result = await db.execute(
            select(ReputationScore).where(ReputationScore.agent_id == agent_id)
        )
        rep = result.scalar_one_or_none()
        if rep:
            rep.score = min(rep.score + self.accept_bonus, 200.0)  # Cap at 200
            rep.total_accepted += 1
            rep.updated_at = datetime.now(timezone.utc)
        else:
            await self.initialize_score(db, agent_id)

    async def record_rejected(self, db: AsyncSession, agent_id: str):
        """Record a rejected instruction — penalize score."""
        result = await db.execute(
            select(ReputationScore).where(ReputationScore.agent_id == agent_id)
        )
        rep = result.scalar_one_or_none()
        if rep:
            rep.score = max(rep.score - self.reject_penalty, 0.0)  # Floor at 0
            rep.total_rejected += 1
            rep.updated_at = datetime.now(timezone.utc)
        else:
            await self.initialize_score(db, agent_id)

    async def get_score(self, db: AsyncSession, agent_id: str) -> Optional[float]:
        """Get current reputation score for an agent."""
        result = await db.execute(
            select(ReputationScore).where(ReputationScore.agent_id == agent_id)
        )
        rep = result.scalar_one_or_none()
        return rep.score if rep else None

    async def get_all_scores(self, db: AsyncSession):
        """Get all reputation scores, ordered by score descending."""
        result = await db.execute(
            select(ReputationScore).order_by(ReputationScore.score.desc())
        )
        return result.scalars().all()

    def needs_scrutiny(self, score: Optional[float]) -> bool:
        """Check if an agent needs heightened scrutiny."""
        if score is None:
            return False
        return score < self.scrutiny_threshold


# Global singleton
reputation_tracker = ReputationTracker()
