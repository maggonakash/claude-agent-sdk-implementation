import logging
import shutil
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import aiofiles

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

from app.agent import (
    run_agent_stream,
    ensure_session_dirs,
    WORKSPACE_DIR,
)
from app.session_store import (
    create_session,
    generate_session_id,
    get_history,
    get_session,
    session_exists,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ALLOWED_EXTENSIONS = {".pptx", ".docx", ".xlsx"}

# Ensure workspace root exists
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Document Agent API",
    description="Upload documents and interact with them via a Claude-powered agent.",
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class AgentResponse(BaseModel):
    session_id: str
    result: str
    files_modified: list[str]
    session_dir: str           # The session root directory


class HistoryEntry(BaseModel):
    role: str
    content: str
    timestamp: str


class SessionInfo(BaseModel):
    session_id: str
    sdk_session_id: str | None
    created_at: str
    updated_at: str
    history: list[HistoryEntry]


class FileInfo(BaseModel):
    name: str
    path: str
    size_bytes: int


class NewSessionResponse(BaseModel):
    session_id: str
    session_dir: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _save_uploads(
    session_id: str, files: list[UploadFile] | None
) -> list[str]:
    """
    Asynchronously validate and save uploaded files to the session's uploads dir.
    Reads in chunks to prevent memory overload and avoid blocking the event loop.
    """
    if not files:
        return []
        
    if not session_exists(WORKSPACE_DIR, session_id):
        create_session(WORKSPACE_DIR, session_id)
        
    _, uploads_dir, _ = ensure_session_dirs(session_id)
    uploaded_names: list[str] = []
    
    for file in files:
        # 1. Validate extension
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File '{file.filename}' has unsupported extension '{ext}'. "
                       f"Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
            )
            
        # 2. Sanitize filename to prevent directory traversal attacks
        safe_filename = Path(file.filename).name
        dest = uploads_dir / safe_filename
        
        # 3. Asynchronously write the file in chunks
        try:
            async with aiofiles.open(dest, "wb") as f:
                # Read in 1MB chunks to keep memory usage stable, 
                # especially important for larger .pptx or .docx files.
                while chunk := await file.read(1024 * 1024):
                    await f.write(chunk)
        except Exception as e:
            logger.error(f"Failed to save file {safe_filename} for session {session_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to save file: {safe_filename}")
        finally:
            # Always close the FastAPI UploadFile to free up underlying spooled resources
            await file.close()
            
        uploaded_names.append(safe_filename)
        
    return uploaded_names

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/sessions", response_model=NewSessionResponse)
async def create_new_session():
    """Pre-generate a session ID and create its workspace directory.

    Creates workspace/{session_id}/uploads/ and workspace/{session_id}/processed/.
    Call this before /agent to get a session_id you control.
    You can then upload files or direct the agent using this ID.
    """
    sid = generate_session_id()
    session_root, _, _ = ensure_session_dirs(sid)
    create_session(WORKSPACE_DIR, sid)
    return NewSessionResponse(session_id=sid, session_dir=str(session_root))


@app.get("/sessions/{session_id}", response_model=SessionInfo)
async def get_session_info(session_id: str):
    """Retrieve full session metadata and conversation history."""
    if not session_exists(WORKSPACE_DIR, session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    data = get_session(WORKSPACE_DIR, session_id)
    return SessionInfo(
        session_id=data["session_id"],
        sdk_session_id=data.get("sdk_session_id"),
        created_at=data["created_at"],
        updated_at=data["updated_at"],
        history=[HistoryEntry(**e) for e in data.get("history", [])],
    )


@app.get("/sessions/{session_id}/history", response_model=list[HistoryEntry])
async def get_session_history(session_id: str):
    """Retrieve just the conversation history for a session."""
    if not session_exists(WORKSPACE_DIR, session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    history = get_history(WORKSPACE_DIR, session_id)
    return [HistoryEntry(**e) for e in history]


@app.post("/agent/stream")
async def agent_stream_endpoint(
    instruction: str = Form(...),
    session_id: Optional[str] = Form(None),
    files: list[UploadFile] = File(default=[]),
):
    """Send an instruction to the Claude agent with real-time SSE streaming.

    Accepts multipart form data:
    - instruction: The natural language instruction (required)
    - session_id: Session ID to resume (optional, omit for new session)
    - files: .pptx/.docx/.xlsx files to upload (optional)

    Returns a Server-Sent Events stream with event types:
    session_start, status, tool_start, tool_end, text_delta, error, result, files, done.
    """
    # If files are provided but no session_id, generate one
    if files and not session_id:
        session_id = generate_session_id()
        logger.info(f"Generated new session_id for upload: {session_id}")

    # Save any uploaded files before starting the stream
    uploaded_names = []
    if session_id and files:
        logger.info(f"Processing {len(files)} uploads for session {session_id}...")
        uploaded_names = await _save_uploads(session_id, files)
        logger.info(f"Saved uploads: {uploaded_names}")
    
    logger.info(f"Starting stream for session={session_id}, instruction='{instruction}'")

    async def event_generator():
        try:
            async for event in run_agent_stream(
                instruction=instruction,
                session_id=session_id,
                uploaded_files=uploaded_names or None,
            ):
                yield event.to_sse()
        except Exception as e:
            logger.error(f"Stream error for session {session_id}: {e}", exc_info=True)
            yield f"data: {{\"type\": \"error\", \"message\": \"Internal stream error: {str(e)}\"}}\n\n"
        finally:
            logger.info(f"Stream finished for session {session_id}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


# ---------------------------------------------------------------------------
# Frontend UI
# ---------------------------------------------------------------------------
STATIC_DIR = Path(__file__).parent / "static"


@app.get("/")
async def serve_ui():
    """Serve the streaming agent UI."""
    return FileResponse(STATIC_DIR / "index.html")


# Mount static files (CSS, JS, etc.) — MUST be after all API routes
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
