# =============================================================================
# Dockerfile — SkillForge AI Assistant
# =============================================================================
# Multi-stage build: dependencies → runtime
#
# Usage:
#   docker build -t skillforge .
#   docker run -v ./data:/app/data -v ./config.py:/app/config.py skillforge gradio
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Build dependencies
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# Copy dependency files first (cache layer)
COPY requirements.txt pyproject.toml ./
COPY src/ src/

# Install package + dependencies
RUN pip install --no-cache-dir -e ".[all]"

# ---------------------------------------------------------------------------
# Stage 2: Runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim

WORKDIR /app

# Install runtime system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ src/
COPY skills/ skills/
COPY pyproject.toml requirements.txt ./

# Install in editable mode (for PROJECT_ROOT resolution)
RUN pip install --no-cache-dir -e .

# Create data directories
RUN mkdir -p data/sessions data/scheduler data/heartbeats data/personality/agents

# Default port for Gradio
EXPOSE 7777

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD curl -f http://localhost:7777/ || exit 1

# Default: run Gradio UI (override with docker run ... telegram/discord/etc)
ENTRYPOINT ["skillforge"]
CMD ["gradio"]
