import json
import logging
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.agent import ensure_session_dirs, run_agent_stream
from app.session_store import (
    create_session,
    generate_session_id,
    get_session,
    session_exists,
    set_session_title,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])

ALLOWED_EXTENSIONS = {".pptx", ".docx", ".xlsx"}


async def _save_uploads(session_id: str, files: list[UploadFile] | None) -> list[str]:
    if not files:
        return []

    if not await session_exists(session_id):
        await create_session(session_id)

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

        safe_filename = Path(file.filename).name
        dest = uploads_dir / safe_filename

        try:
            async with aiofiles.open(dest, "wb") as f:
                while chunk := await file.read(1024 * 1024):
                    await f.write(chunk)
        except Exception as e:
            logger.error(f"Failed to save file {safe_filename} for session {session_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to save file: {safe_filename}")
        finally:
            await file.close()

        uploaded_names.append(safe_filename)

    return uploaded_names


@router.post("/stream")
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
    if files and not session_id:
        session_id = generate_session_id()
        logger.info(f"Generated new session_id for upload: {session_id}")

    uploaded_names = []
    if session_id and files:
        logger.info(f"Processing {len(files)} uploads for session {session_id}...")
        uploaded_names = await _save_uploads(session_id, files)
        logger.info(f"Saved uploads: {uploaded_names}")

    logger.info(f"Starting stream for session={session_id}, instruction='{instruction}'")

    # Set title immediately (before stream starts) if session has no title yet.
    # This ensures the sidebar shows the correct title as soon as the user sends a message.
    if session_id:
        existing = await get_session(session_id) if await session_exists(session_id) else None
        if existing is None or existing.get("title") is None:
            await set_session_title(session_id, instruction[:80].strip())
            logger.info(f"Title set for session {session_id}: '{instruction[:80].strip()}'")

    async def event_generator():
        nonlocal session_id

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
            "X-Accel-Buffering": "no",
        },
    )
