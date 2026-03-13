FROM python:3.12-slim-bookworm

# Install system dependencies
# - curl/git: for downloading tools
# - nodejs/npm: for @anthropic-ai/claude-code
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Install Claude Code CLI globally (required by claude-agent-sdk)
RUN npm install -g @anthropic-ai/claude-code

# Create a non-root user
RUN useradd -m -u 1000 appuser

# Set working directory
WORKDIR /app

# Copy dependency files first (for caching)
COPY pyproject.toml uv.lock ./

# Install dependencies
# --frozen: ensure lockfile is respected
# --no-dev: exclude dev dependencies
# --no-install-project: install only dependencies, not the project itself yet
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code
COPY app/ ./app/

# Create workspace directories
RUN mkdir -p /workspace/uploads /workspace/processed && \
    chown -R appuser:appuser /app /workspace

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Run the server using 'uv run' to ensure environment is activated
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
