from fastapi import APIRouter, HTTPException, Query

from app.agent import ensure_session_dirs
from app.schemas.session import (
    HistoryEntry,
    NewSessionResponse,
    PaginatedHistory,
    PaginatedSessions,
    SessionInfo,
    SessionSummary,
    UpdateSessionRequest,
)
from app.session_store import (
    create_session,
    generate_session_id,
    get_history_paginated,
    get_session,
    list_sessions_paginated,
    session_exists,
    set_session_title,
    soft_delete_session,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=NewSessionResponse)
async def create_new_session():
    """Pre-generate a session ID and create its workspace directory."""
    sid = generate_session_id()
    session_root, _, _ = ensure_session_dirs(sid)
    await create_session(sid)
    return NewSessionResponse(session_id=sid, session_dir=str(session_root))


@router.get("", response_model=PaginatedSessions)
async def list_sessions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """Return a paginated list of all sessions, sorted by most recently updated."""
    result = await list_sessions_paginated(page=page, page_size=page_size)
    return PaginatedSessions(
        sessions=[SessionSummary(**s) for s in result["sessions"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        has_more=result["has_more"],
    )


@router.get("/{session_id}", response_model=SessionInfo)
async def get_session_info(session_id: str):
    """Retrieve full session metadata and conversation history."""
    if not await session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    data = await get_session(session_id)
    return SessionInfo(
        session_id=data["session_id"],
        sdk_session_id=data.get("sdk_session_id"),
        title=data.get("title"),
        created_at=data["created_at"],
        updated_at=data["updated_at"],
        history=[HistoryEntry(**e) for e in data.get("history", [])],
    )


@router.get("/{session_id}/history", response_model=PaginatedHistory)
async def get_session_history(
    session_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """Return paginated conversation history for a session (most recent page first)."""
    if not await session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    result = await get_history_paginated(session_id, page=page, page_size=page_size)
    return PaginatedHistory(
        history=[HistoryEntry(**e) for e in result["history"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        has_more=result["has_more"],
    )


@router.patch("/{session_id}", response_model=SessionSummary)
async def rename_session(session_id: str, body: UpdateSessionRequest):
    """Update the title of a session."""
    if not await session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    await set_session_title(session_id, body.title.strip())
    data = await get_session(session_id)
    return SessionSummary(
        session_id=data["session_id"],
        title=data.get("title"),
        created_at=data["created_at"],
        updated_at=data["updated_at"],
    )


@router.delete("/{session_id}", status_code=200)
async def delete_session(session_id: str):
    """Soft-delete a session (sets is_deleted=True). It will no longer appear in session listings."""
    if not await session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    await soft_delete_session(session_id)
    return {"status": "deleted", "session_id": session_id}
