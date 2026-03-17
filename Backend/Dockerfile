FROM python:3.12-slim

# Install system dependencies (needed for claude-agent-sdk / Claude Code CLI)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI globally (required by claude-agent-sdk)
RUN npm install -g @anthropic-ai/claude-code

# Create a non-root user
RUN useradd -m -u 1000 appuser

# Set working directory for the app
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install Python dependencies using uv sync
COPY pyproject.toml uv.lock ./
# First sync: install dependencies only (caching layer)
RUN uv sync --frozen --no-install-project --no-dev

# Copy application code
COPY app/ ./app/

# Second sync: install the project itself (if applicable) and ensure everything is up-to-date
RUN uv sync --frozen --no-dev

# Put the uv virtual environment on the PATH so `uvicorn` and `python` use it automatically
ENV PATH="/app/.venv/bin:$PATH"

# Create the workspace directories where uploaded files live
RUN mkdir -p /workspace/uploads /workspace/processed

# Change ownership of app and workspace directories to the non-root user
RUN chown -R appuser:appuser /app /workspace

# Switch to the non-root user
USER appuser

# Expose FastAPI port
EXPOSE 8000

# Run the server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
