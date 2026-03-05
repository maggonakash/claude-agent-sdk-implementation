import logging
import os
import shutil
from pathlib import Path

from fastapi import FastAPI, UploadFile, HTTPException, Form, File
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.agent import run_agent as execute_agent, run_agent_stream
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
WORKSPACE_DIR = Path(os.getenv("WORKSPACE_DIR", "./workspace")).resolve()

ALLOWED_EXTENSIONS = {".pptx", ".docx", ".xlsx"}

# Ensure workspace exists
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
class AgentRequest(BaseModel):
    instruction: str
    session_id: str | None = None  # None = new session, str = resume


class AgentResponse(BaseModel):
    session_id: str
    result: str
    files_modified: list[str]
    session_dir: str           # The session-specific output directory


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
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/sessions", response_model=NewSessionResponse)
async def create_new_session():
    """Pre-generate a session ID and create its workspace directory.

    Call this before /agent to get a session_id you control.
    You can then upload files or direct the agent using this ID.
    """
    sid = generate_session_id()
    session_root = WORKSPACE_DIR / sid
    
    (session_root / "uploads").mkdir(parents=True, exist_ok=True)
    (session_root / "processed").mkdir(parents=True, exist_ok=True)
    
    # Session record is created lazily by the agent on first use,
    # but we can also create it eagerly here.
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
    """List files produced by a specific session."""
    processed_dir = WORKSPACE_DIR / session_id / "processed"
    if not processed_dir.exists():
        raise HTTPException(status_code=404, detail=f"Session directory not found")
    results: list[FileInfo] = []
    for item in processed_dir.rglob("*"):
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
    """Upload one or more .pptx, .docx, or .xlsx files to the session workspace."""
    uploaded: list[FileInfo] = []
    
    uploads_dir = WORKSPACE_DIR / session_id / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    for file in files:
        # Validate extension
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File '{file.filename}' has unsupported extension '{ext}'. "
                       f"Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
            )

        # Save to uploads directory
        dest = uploads_dir / file.filename
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)

        uploaded.append(
            FileInfo(
                name=file.filename,
                path=str(dest),
                size_bytes=dest.stat().st_size,
            )
        )

    return uploaded


@app.get("/files", response_model=list[FileInfo])
async def list_files():
    """List all files across all sessions."""
    results: list[FileInfo] = []

    for item in WORKSPACE_DIR.rglob("*"):
        if item.is_file() and not item.name.endswith(".json"): # Exclude session metadata
             results.append(
                FileInfo(
                    name=item.name,
                    path=str(item),
                    size_bytes=item.stat().st_size,
                )
            )

    return results


@app.post("/agent", response_model=AgentResponse)
async def agent_endpoint(
    instruction: str = Form(...),
    session_id: str | None = Form(None),
    files: list[UploadFile] = File(None),
):
    """Send an instruction to the Claude agent. Optionally resume a session.

    This is the blocking (non-streaming) endpoint. For real-time progress
    updates, use POST /agent/stream instead.
    """
    try:
        # 1. Session setup
        if session_id is None:
            session_id = generate_session_id()
            create_session(WORKSPACE_DIR, session_id)

        # 2. Handle uploads
        uploaded_names = []
        if files:
            uploads_dir = WORKSPACE_DIR / session_id / "uploads"
            uploads_dir.mkdir(parents=True, exist_ok=True)
            for file in files:
                # Validate extension
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

        # 3. Run agent
        result = await execute_agent(
            instruction=instruction,
            session_id=session_id,
            uploaded_files=uploaded_names,
        )
        session_root = str(WORKSPACE_DIR / result.session_id)

        # Surface agent-level errors as HTTP errors
        if result.is_error:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": result.error_detail,
                    "result": result.result,
                    "session_id": result.session_id,
                    "files_modified": result.files_modified,
                    "session_dir": session_root,
                },
            )

        return AgentResponse(
            session_id=result.session_id,
            result=result.result,
            files_modified=result.files_modified,
            session_dir=session_root,
        )
    except HTTPException:
        raise  # Re-raise our own HTTPExceptions
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
    session_id: str | None = Form(None),
    files: list[UploadFile] = File(None),
):
    """Send an instruction to the Claude agent with real-time SSE streaming.

    Returns a Server-Sent Events stream. Each event is a JSON object with
    a "type" field indicating the event kind:

    - session_start:  {"type": "session_start", "session_id": "..."}
    - status:         {"type": "status", "message": "Agent initialized", ...}
    - tool_start:     {"type": "tool_start", "tool": "Bash", ...}
    - tool_end:       {"type": "tool_end", "tool": "Bash", "summary": "npm install", ...}
    - text_delta:     {"type": "text_delta", "text": "partial text...", ...}
    - error:          {"type": "error", "message": "...", ...}
    - result:         {"type": "result", "status": "success", "result": "...", ...}
    - files:          {"type": "files", "files_modified": [...], ...}
    - done:           {"type": "done", "session_id": "..."}

    Connect with EventSource or any SSE client:
        const es = new EventSource('/agent/stream', { method: 'POST', body: ... });
    Or use fetch() and read the response body as a stream.
    """

    # 1. Session setup
    if session_id is None:
        session_id = generate_session_id()
        create_session(WORKSPACE_DIR, session_id)

    # 2. Handle uploads
    uploaded_names = []
    if files:
        uploads_dir = WORKSPACE_DIR / session_id / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        for file in files:
            # Validate extension
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

    async def event_generator():
        async for event in run_agent_stream(
            instruction=instruction,
            session_id=session_id,
            uploaded_files=uploaded_names,
        ):
            yield event.to_sse()

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
