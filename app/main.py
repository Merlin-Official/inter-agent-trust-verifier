"""
Inter-Agent Trust Verifier — Main Application Entry Point

A production-ready inter-agent trust protocol that allows agents to verify
the legitimacy, authority, and policy-compliance of instructions received
from other agents before executing them.

PS-5.2 | Aivar Innovations Agentic AI Task
"""

import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import init_db, close_db
from app.middleware import RequestLoggingMiddleware
from app.core.revocation import revocation_manager
from app.database import async_session_factory

# Import all API routers
from app.api.agents import router as agents_router
from app.api.delegation import router as delegation_router
from app.api.instructions import router as instructions_router
from app.api.revocation import router as revocation_router
from app.api.audit import router as audit_router
from app.api.health import router as health_router

import logging

settings = get_settings()

# ─── Configure structured logging ─────────────────────────────────────
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if settings.ENVIRONMENT == "development"
        else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        logging.getLevelName(settings.LOG_LEVEL)
    ),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


# ─── App lifecycle ────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logger.info("starting_application", environment=settings.ENVIRONMENT)

    # Initialize database
    await init_db()
    logger.info("database_initialized")

    # Load revocation state into memory
    async with async_session_factory() as session:
        await revocation_manager.load_from_db(session)
    logger.info("revocation_list_loaded")

    yield

    # Shutdown
    await close_db()
    logger.info("application_shutdown")


# ─── Create FastAPI app ───────────────────────────────────────────────
app = FastAPI(
    title="Inter-Agent Trust Verifier",
    description=(
        "A production-ready inter-agent trust protocol that allows agents to "
        "verify the legitimacy, authority, and policy-compliance of instructions "
        "received from other agents before executing them.\n\n"
        "**PS-5.2** | Aivar Innovations — Agentic AI Security"
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── Middleware ────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)


# ─── Global exception handler ─────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "unhandled_exception",
        error=str(exc),
        path=request.url.path,
        method=request.method,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": str(exc) if settings.ENVIRONMENT == "development" else "An unexpected error occurred",
        },
    )


# ─── Register routers ─────────────────────────────────────────────────
app.include_router(agents_router)
app.include_router(delegation_router)
app.include_router(instructions_router)
app.include_router(revocation_router)
app.include_router(audit_router)
app.include_router(health_router)


# ─── Root endpoint ────────────────────────────────────────────────────
@app.get("/", tags=["Root"])
async def root():
    return {
        "name": "Inter-Agent Trust Verifier",
        "version": "1.0.0",
        "description": "PS-5.2 — Agentic AI Security",
        "docs": "/docs",
        "health": "/health",
    }
