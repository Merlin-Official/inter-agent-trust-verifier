"""
Pydantic schemas for API request and response models.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ─── Agent Schemas ────────────────────────────────────────────────────

class AgentRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Unique agent name")
    description: Optional[str] = Field(None, description="Agent description")
    policy_scope: List[str] = Field(
        default=["*"],
        description="List of actions this agent is allowed to execute (receiver policy)",
    )


class AgentResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    public_key: str
    status: str
    policy_scope: List[str]
    created_at: datetime


class AgentRegisterResponse(BaseModel):
    agent: AgentResponse
    private_key: str = Field(..., description="SAVE THIS — it is never stored on the server")
    message: str


# ─── Delegation Schemas ──────────────────────────────────────────────

class DelegationCreateRequest(BaseModel):
    issuer_id: str = Field(..., description="Agent or admin issuing the delegation")
    issuer_private_key: str = Field(..., description="Issuer's private key for signing")
    subject_id: str = Field(..., description="Agent receiving the delegation")
    allowed_actions: List[str] = Field(..., description="Actions the subject is allowed to instruct")
    allowed_targets: Optional[List[str]] = Field(None, description="Optional target agent restrictions")
    expires_in_hours: float = Field(default=24.0, description="Hours until expiration")


class DelegationResponse(BaseModel):
    token_id: str
    issuer_id: str
    subject_id: str
    allowed_actions: List[str]
    allowed_targets: Optional[List[str]]
    expires_at: str
    is_revoked: bool
    signature: str
    created_at: datetime


# ─── Instruction Schemas ─────────────────────────────────────────────

class InstructionSignRequest(BaseModel):
    sender_id: str
    sender_private_key: str = Field(..., description="Sender's private key for signing")
    receiver_id: str
    action: str
    delegation_token_id: str
    payload: Optional[dict] = None


class SignedInstructionResponse(BaseModel):
    instruction_id: str
    sender_id: str
    receiver_id: str
    action: str
    payload: Optional[dict]
    delegation_token_id: str
    timestamp: str
    signature: str


class InstructionVerifyRequest(BaseModel):
    """Send a signed instruction for verification and optional execution."""
    instruction_id: str
    sender_id: str
    receiver_id: str
    action: str
    payload: Optional[dict] = None
    delegation_token_id: str
    timestamp: str
    signature: str


class VerificationCheckResponse(BaseModel):
    name: str
    passed: bool
    detail: str


class VerificationResponse(BaseModel):
    accepted: bool
    instruction_id: str
    checks: List[VerificationCheckResponse]
    rejection_reason: Optional[str] = None
    llm_explanation: Optional[str] = None
    timestamp: str


# ─── Revocation Schemas ──────────────────────────────────────────────

class RevokeAgentRequest(BaseModel):
    reason: str = Field(..., description="Reason for revocation")
    revoked_by: str = Field(default="admin", description="Who is revoking")


class RevocationStatusResponse(BaseModel):
    agent_id: str
    agent_name: str
    status: str
    revocation_history: list


# ─── Audit Schemas ───────────────────────────────────────────────────

class AuditLogResponse(BaseModel):
    id: str
    instruction_id: str
    sender_id: str
    sender_name: Optional[str]
    receiver_id: str
    receiver_name: Optional[str]
    action: str
    outcome: str
    reason: Optional[str]
    checks_passed: Optional[list]
    checks_failed: Optional[list]
    timestamp: datetime


# ─── Reputation Schemas ──────────────────────────────────────────────

class ReputationResponse(BaseModel):
    agent_id: str
    agent_name: Optional[str] = None
    score: float
    total_accepted: int
    total_rejected: int
    needs_scrutiny: bool
    updated_at: datetime


# ─── Health Schemas ──────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    environment: str
    database: str
    llm_available: bool
    uptime_seconds: float
    timestamp: str


# ─── Stats Schemas ───────────────────────────────────────────────────

class DashboardStatsResponse(BaseModel):
    total_agents: int
    active_agents: int
    revoked_agents: int
    suspended_agents: int
    total_instructions: int
    total_accepted: int
    total_rejected: int
    acceptance_rate: float
