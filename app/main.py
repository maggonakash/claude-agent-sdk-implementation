import logging
import shutil
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
# ... imports ...

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.agent import (
    run_agent as execute_agent,
    run_agent_stream,
    ensure_session_dirs,
    get_session_paths,
    WORKSPACE_DIR,
)
from app.session_store import (
    create_session,
    generate_session_id,
    get_history,
    get_session,
    session_exists,
)

logger = logging.getLogger(__name__)

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
    """Validate and save uploaded files to the session's uploads dir.

    Returns the list of saved filenames.
    """
    if not files:
        return []
    if not session_exists(WORKSPACE_DIR, session_id):
        create_session(WORKSPACE_DIR, session_id)
    _, uploads_dir, _ = ensure_session_dirs(session_id)
    uploaded_names: list[str] = []
    for file in files:
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File '{file.filename}' has unsupported extension '{ext}'. "
                       f"Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
            )
        dest = uploads_dir / file.filename
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
        uploaded_names.append(file.filename)
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


@app.get("/sessions/{session_id}/files", response_model=list[FileInfo])
async def list_session_files(session_id: str):
    """List all files in a session (uploads + processed)."""
    session_root, uploads_dir, processed_dir = get_session_paths(session_id)
    if not session_root.exists():
        raise HTTPException(status_code=404, detail="Session directory not found")
    results: list[FileInfo] = []
    for directory in [uploads_dir, processed_dir]:
        if directory.exists():
            for item in directory.rglob("*"):
                if item.is_file():
                    results.append(
                        FileInfo(
                            name=item.name,
                            path=str(item),
                            size_bytes=item.stat().st_size,
                        )
                    )
    return results


@app.get("/sessions/{session_id}/uploads", response_model=list[FileInfo])
async def list_session_uploads(session_id: str):
    """List uploaded files for a specific session."""
    _, uploads_dir, _ = get_session_paths(session_id)
    if not uploads_dir.exists():
        raise HTTPException(status_code=404, detail="Session uploads directory not found")
    results: list[FileInfo] = []
    for item in uploads_dir.iterdir():
        if item.is_file():
            results.append(
                FileInfo(
                    name=item.name,
                    path=str(item),
                    size_bytes=item.stat().st_size,
                )
            )
    return results


@app.post("/sessions/{session_id}/upload", response_model=list[FileInfo])
async def upload_session_files(session_id: str, files: list[UploadFile]):
    """Upload one or more .pptx, .docx, or .xlsx files to a session's uploads dir."""
    uploaded_names = await _save_uploads(session_id, files)
    # Return full FileInfo for each uploaded file
    _, uploads_dir, _ = get_session_paths(session_id)
    return [
        FileInfo(
            name=name,
            path=str(uploads_dir / name),
            size_bytes=(uploads_dir / name).stat().st_size,
        )
        for name in uploaded_names
    ]


@app.post("/agent", response_model=AgentResponse)
async def agent_endpoint(
    instruction: str = Form(...),
    session_id: Optional[str] = Form(None),
    files: list[UploadFile] = File(default=[]),
):
    """Send an instruction to the Claude agent. Optionally upload files and/or resume a session.

    Accepts multipart form data:
    - instruction: The natural language instruction (required)
    - session_id: Session ID to resume (optional, omit for new session)
    - files: .pptx/.docx/.xlsx files to upload (optional)

    This is the blocking (non-streaming) endpoint. For real-time progress
    updates, use POST /agent/stream instead.
    """
    try:
        # If files are provided but no session_id, generate one
        if files and not session_id:
            session_id = generate_session_id()

        # Save any uploaded files
        uploaded_names = await _save_uploads(session_id, files) if session_id and files else []

        result = await execute_agent(
            instruction=instruction,
            session_id=session_id,
            uploaded_files=uploaded_names or None,
        )
        session_root, _, _ = get_session_paths(result.session_id)

        # Surface agent-level errors as HTTP errors
        if result.is_error:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": result.error_detail,
                    "result": result.result,
                    "session_id": result.session_id,
                    "files_modified": result.files_modified,
                    "session_dir": str(session_root),
                },
            )

        return AgentResponse(
            session_id=result.session_id,
            result=result.result,
            files_modified=result.files_modified,
            session_dir=str(session_root),
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )
    except Exception as e:
        logger.exception("Agent execution failed")
        raise HTTPException(
            status_code=500,
            detail=f"Agent execution failed: {str(e)}",
        )


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
