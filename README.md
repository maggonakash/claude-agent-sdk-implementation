# Claude Agent SDK Implementation

This project implements a document processing agent using the Claude Agent SDK and FastAPI.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) installed
- Python 3.12+

## Setup

1. Install dependencies:
   ```bash
   uv sync
   ```

## Running the Application

To start the development server:

```bash
uv run uvicorn app.main:app --reload
```

The application will be available at `http://localhost:8000`.
- API documentation: `http://localhost:8000/docs`
- Frontend UI: `http://localhost:8000`

## Features

- Upload and process documents (.docx, .pptx, .xlsx)
- Streaming agent responses via SSE
- Persistent session history
- File isolation per session

## Project Structure

- `app/`: Application source code
  - `agent.py`: Agent logic and configuration
  - `main.py`: FastAPI application and endpoints
  - `session_store.py`: Session management
  - `static/`: Frontend assets
- `workspace/`: Data directory (created at runtime)
