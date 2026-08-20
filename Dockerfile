# ============================================
# Inter-Agent Trust Verifier — API Dockerfile
# Multi-stage build for the Python FastAPI service
# ============================================

# ─── Stage 1: Builder ────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ─── Stage 2: Runtime ────────────────────────────────
FROM python:3.11-slim AS runtime

# Security: non-root user
RUN groupadd --system app && useradd --system --gid app app

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY app/ app/
COPY .env.example .env

# Create data directory for SQLite (dev fallback)
RUN mkdir -p /app/data && chown -R app:app /app

USER app

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Start with uvicorn
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
