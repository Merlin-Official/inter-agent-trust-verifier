"""
SQLAlchemy models for the Inter-Agent Trust Verifier.

Tables:
- agents: Registered agents with their public keys and status
- delegation_tokens: Authorization tokens defining what one agent can instruct another to do
- instructions: Persisted signed instructions
- revocations: Record of revoked agent credentials
- audit_logs: Every verification outcome logged
- reputation_scores: Trust scores per agent
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Enum as SAEnum,
    Index,
)
from sqlalchemy.orm import relationship
from app.database import Base
import enum


# ─── Enums ────────────────────────────────────────────────────────────

class AgentStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"


class VerificationOutcome(str, enum.Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


# ─── Models ───────────────────────────────────────────────────────────

class Agent(Base):
    """An agent registered in the trust system."""
    __tablename__ = "agents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    public_key = Column(Text, nullable=False)
    status = Column(
        SAEnum(AgentStatus, native_enum=False),
        default=AgentStatus.ACTIVE,
        nullable=False,
    )
    policy_scope = Column(JSON, nullable=False, default=list)
    # policy_scope example: ["send_email", "read_data", "generate_report"]
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    issued_delegations = relationship(
        "DelegationToken",
        foreign_keys="DelegationToken.issuer_id",
        back_populates="issuer",
    )
    received_delegations = relationship(
        "DelegationToken",
        foreign_keys="DelegationToken.subject_id",
        back_populates="subject",
    )
    reputation = relationship("ReputationScore", back_populates="agent", uselist=False)

    def __repr__(self):
        return f"<Agent(id={self.id}, name={self.name}, status={self.status})>"


class DelegationToken(Base):
    """
    Authorization token granting one agent permission to instruct another.
    Signed by the issuer (or system admin).
    """
    __tablename__ = "delegation_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    issuer_id = Column(String(36), ForeignKey("agents.id"), nullable=False, index=True)
    subject_id = Column(String(36), ForeignKey("agents.id"), nullable=False, index=True)
    allowed_actions = Column(JSON, nullable=False, default=list)
    # allowed_actions example: ["send_email", "read_data"]
    allowed_targets = Column(JSON, nullable=True, default=list)
    # allowed_targets: optional list of specific target agent IDs
    expires_at = Column(String(50), nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)
    signature = Column(Text, nullable=True)
    # signature: the issuer's signature over the token content
    created_at = Column(String(50), default=lambda: datetime.now(timezone.utc).isoformat())

    # Relationships
    issuer = relationship("Agent", foreign_keys=[issuer_id], back_populates="issued_delegations")
    subject = relationship("Agent", foreign_keys=[subject_id], back_populates="received_delegations")

    def __repr__(self):
        return f"<DelegationToken(id={self.id}, issuer={self.issuer_id} → subject={self.subject_id})>"


class Instruction(Base):
    """A persisted signed instruction between agents."""
    __tablename__ = "instructions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sender_id = Column(String(36), ForeignKey("agents.id"), nullable=False, index=True)
    receiver_id = Column(String(36), ForeignKey("agents.id"), nullable=False, index=True)
    action = Column(String(255), nullable=False)
    payload = Column(JSON, nullable=True)
    delegation_token_id = Column(String(36), ForeignKey("delegation_tokens.id"), nullable=False)
    timestamp = Column(String(50), default=lambda: datetime.now(timezone.utc).isoformat())
    signature = Column(Text, nullable=False)
    verification_outcome = Column(String(8))
    created_at = Column(String(50), default=lambda: datetime.now(timezone.utc).isoformat())

    # Relationships
    sender = relationship("Agent", foreign_keys=[sender_id])
    receiver = relationship("Agent", foreign_keys=[receiver_id])
    delegation_token = relationship("DelegationToken")

    def __repr__(self):
        return f"<Instruction(id={self.id}, {self.sender_id} → {self.receiver_id}, action={self.action})>"


class RevocationRecord(Base):
    """Record of agent credential revocations."""
    __tablename__ = "revocations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=False, index=True)
    reason = Column(Text, nullable=False)
    revoked_by = Column(String(255), nullable=False, default="system")
    revoked_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    agent = relationship("Agent")

    def __repr__(self):
        return f"<RevocationRecord(agent={self.agent_id}, reason={self.reason})>"


class AuditLog(Base):
    """Every verification outcome is logged here."""
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    instruction_id = Column(String(36), nullable=False, index=True)
    sender_id = Column(String(36), nullable=False)
    sender_name = Column(String(255), nullable=True)
    receiver_id = Column(String(36), nullable=False)
    receiver_name = Column(String(255), nullable=True)
    action = Column(String(255), nullable=False)
    outcome = Column(
        SAEnum(VerificationOutcome, native_enum=False),
        nullable=False,
    )
    reason = Column(Text, nullable=True)
    checks_passed = Column(JSON, nullable=True, default=list)
    checks_failed = Column(JSON, nullable=True, default=list)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_audit_logs_timestamp", "timestamp"),
        Index("ix_audit_logs_outcome", "outcome"),
    )

    def __repr__(self):
        return f"<AuditLog(instruction={self.instruction_id}, outcome={self.outcome})>"


class ReputationScore(Base):
    """Trust reputation score per agent."""
    __tablename__ = "reputation_scores"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), ForeignKey("agents.id"), unique=True, nullable=False, index=True)
    score = Column(Float, default=100.0, nullable=False)
    total_accepted = Column(Integer, default=0, nullable=False)
    total_rejected = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    agent = relationship("Agent", back_populates="reputation")

    def __repr__(self):
        return f"<ReputationScore(agent={self.agent_id}, score={self.score})>"
