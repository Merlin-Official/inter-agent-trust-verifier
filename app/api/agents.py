"""
Agent registration and management endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import Agent, AgentStatus
from app.core.crypto import generate_keypair
from app.core.reputation import reputation_tracker
from app.api.schemas import (
    AgentRegisterRequest,
    AgentRegisterResponse,
    AgentResponse,
)

router = APIRouter(prefix="/api/v1/agents", tags=["Agents"])


@router.post(
    "/register",
    response_model=AgentRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new agent",
)
async def register_agent(
    request: AgentRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new agent in the trust system.

    Generates an Ed25519 keypair. The private key is returned ONCE
    and must be saved by the caller — it is never stored on the server.
    """
    # Check for duplicate name
    existing = await db.execute(
        select(Agent).where(Agent.name == request.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Agent with name '{request.name}' already exists",
        )

    # Generate keypair
    private_key, public_key = generate_keypair()

    # Create agent
    agent = Agent(
        name=request.name,
        description=request.description,
        public_key=public_key,
        status=AgentStatus.ACTIVE,
        policy_scope=request.policy_scope,
    )
    db.add(agent)
    await db.flush()

    # Initialize reputation score
    await reputation_tracker.initialize_score(db, agent.id)

    return AgentRegisterResponse(
        agent=AgentResponse(
            id=agent.id,
            name=agent.name,
            description=agent.description,
            public_key=agent.public_key,
            status=agent.status.value,
            policy_scope=agent.policy_scope,
            created_at=agent.created_at,
        ),
        private_key=private_key,
        message="Agent registered. SAVE the private_key — it is never stored on the server.",
    )


@router.get(
    "",
    response_model=list[AgentResponse],
    summary="List all agents",
)
async def list_agents(
    db: AsyncSession = Depends(get_db),
):
    """List all registered agents."""
    result = await db.execute(select(Agent).order_by(Agent.created_at.desc()))
    agents = result.scalars().all()
    return [
        AgentResponse(
            id=a.id,
            name=a.name,
            description=a.description,
            public_key=a.public_key,
            status=a.status.value,
            policy_scope=a.policy_scope,
            created_at=a.created_at,
        )
        for a in agents
    ]


@router.get(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Get agent details",
)
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get details for a specific agent."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found",
        )
    return AgentResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        public_key=agent.public_key,
        status=agent.status.value,
        policy_scope=agent.policy_scope,
        created_at=agent.created_at,
    )
