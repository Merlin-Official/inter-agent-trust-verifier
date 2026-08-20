"""
Health check and readiness endpoints.
"""

import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import get_settings
from app.core.llm_policy import llm_analyzer
from app.api.schemas import HealthResponse

router = APIRouter(tags=["Health"])
_start_time = time.time()
settings = get_settings()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
)
async def health_check(
    db: AsyncSession = Depends(get_db),
):
    """
    Basic health check.
    Returns system status including DB connectivity and LLM availability.
    """
    # Check database
    db_status = "connected"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "disconnected"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        environment=settings.ENVIRONMENT,
        database=db_status,
        llm_available=llm_analyzer.is_available,
        uptime_seconds=round(time.time() - _start_time, 2),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get(
    "/ready",
    summary="Readiness probe",
)
async def readiness_check(
    db: AsyncSession = Depends(get_db),
):
    """Readiness probe for container orchestrators (ECS, K8s)."""
    try:
        await db.execute(text("SELECT 1"))
        return {"ready": True}
    except Exception:
        return {"ready": False}
