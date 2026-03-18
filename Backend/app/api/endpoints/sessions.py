from fastapi import APIRouter, Depends, HTTPException, Query

from app.agent import ensure_session_dirs
from app.core.dependencies import get_current_user
from app.db.sessions import (
    create_session,
    generate_session_id,
    get_session,
    list_sessions_paginated,
    session_belongs_to_user,
    session_exists,
    set_session_title,
    soft_delete_session,
    update_session,
)
from app.db.artifacts import get_artifacts_by_messages
from app.db.messages import get_messages_paginated
from app.schemas.session import (
    NewSessionResponse,
    PaginatedSessions,
    SessionSummary,
    UpdateSessionRequest,
)
from app.schemas.message import PaginatedMessages, MessageOut

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=NewSessionResponse)
async def create_new_session(current_user: dict = Depends(get_current_user)):
    """Pre-generate a session ID for the current user."""
    sid = generate_session_id()
    session_root, _, _, _ = ensure_session_dirs(sid)
    await create_session(sid, current_user["user_id"], current_user["email"])
    return NewSessionResponse(session_id=sid, session_dir=str(session_root))


@router.get("", response_model=PaginatedSessions)
async def list_sessions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """Return paginated sessions belonging to the current user."""
    result = await list_sessions_paginated(current_user["user_id"], page=page, page_size=page_size)
    return PaginatedSessions(
        sessions=[SessionSummary(**s) for s in result["sessions"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        has_more=result["has_more"],
    )


@router.patch("/{session_id}", response_model=SessionSummary)
async def rename_session(
    session_id: str,
    body: UpdateSessionRequest,
    current_user: dict = Depends(get_current_user),
):
    """Rename a session title."""
    await _assert_session_access(session_id, current_user["user_id"])
    await set_session_title(session_id, body.title.strip())
    data = await get_session(session_id)
    return SessionSummary(
        session_id=data["session_id"],
        title=data.get("title"),
        created_at=data["created_at"],
        updated_at=data["updated_at"],
    )


@router.delete("/{session_id}", status_code=200)
async def delete_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Soft-delete a session."""
    await _assert_session_access(session_id, current_user["user_id"])
    await soft_delete_session(session_id)
    return {"status": "deleted", "session_id": session_id}


@router.get("/{session_id}/messages", response_model=PaginatedMessages)
async def get_session_messages(
    session_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """Return paginated messages (turns) for a session."""
    await _assert_session_access(session_id, current_user["user_id"])
    result = await get_messages_paginated(session_id, page=page, page_size=page_size)

    # Batch-fetch artifacts for all messages in this page
    message_ids = [m["message_id"] for m in result["messages"]]
    artifacts_map = await get_artifacts_by_messages(message_ids)

    messages_out = []
    for m in result["messages"]:
        m["artifacts"] = artifacts_map.get(m["message_id"], [])
        messages_out.append(MessageOut(**m))

    return PaginatedMessages(
        messages=messages_out,
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        has_more=result["has_more"],
    )


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

async def _assert_session_access(session_id: str, user_id: str):
    if not await session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    if not await session_belongs_to_user(session_id, user_id):
        raise HTTPException(status_code=403, detail="Access denied")
