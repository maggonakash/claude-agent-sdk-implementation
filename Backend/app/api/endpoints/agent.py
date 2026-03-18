import json
import logging
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.agent import ensure_session_dirs, run_agent_stream
from app.core.dependencies import get_current_user
from app.db.sessions import (
    create_session,
    generate_session_id,
    get_session,
    session_belongs_to_user,
    session_exists,
    set_session_title,
)
from app.db.messages import create_message, update_message_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])

ALLOWED_EXTENSIONS = {".pptx", ".docx", ".xlsx", ".pdf", ".jpeg", ".jpg", ".png"}


async def _save_uploads(session_id: str, files: list[UploadFile] | None) -> list[str]:
    if not files:
        return []

    if not await session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    _, user_uploads, _, _ = ensure_session_dirs(session_id)
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
        dest = user_uploads / safe_filename

        try:
            async with aiofiles.open(dest, "wb") as f:
                while chunk := await file.read(1024 * 1024):
                    await f.write(chunk)
        except Exception as e:
            logger.error(f"Failed to save file {safe_filename}: {e}")
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
    current_user: dict = Depends(get_current_user),
):
    """Stream agent responses via SSE. Requires authentication."""

    user_id = current_user["user_id"]
    user_email = current_user["email"]

    # Generate session if not provided
    if not session_id:
        session_id = generate_session_id()
        logger.info(f"Generated new session_id: {session_id}")

    # Ensure session exists and belongs to current user
    if await session_exists(session_id):
        if not await session_belongs_to_user(session_id, user_id):
            raise HTTPException(status_code=403, detail="Access denied to this session")
    else:
        await create_session(session_id, user_id, user_email)

    # Handle file uploads
    uploaded_names: list[str] = []
    if files:
        logger.info(f"Processing {len(files)} uploads for session {session_id}...")
        uploaded_names = await _save_uploads(session_id, files)

    # Set session title from first message if not yet set
    existing = await get_session(session_id)
    if existing is None or existing.get("title") is None:
        await set_session_title(session_id, instruction[:80].strip())

    # Create the message document immediately (user side)
    message_doc = await create_message(
        conversation_id=session_id,
        user_id=user_id,
        user_email=user_email,
        user_message=instruction,
        files_uploaded=uploaded_names,
    )
    message_id = message_doc["message_id"]

    logger.info(f"Starting stream for session={session_id}, message_id={message_id}")

    async def event_generator():
        accumulated_text = ""
        is_error = False
        error_msg = None
        turns_used = None
        cost_usd = None

        # Emit message_id immediately so the frontend can attach feedback
        yield f'data: {{"type": "message_created", "message_id": "{message_id}"}}\n\n'

        try:
            async for event in run_agent_stream(
                instruction=instruction,
                session_id=session_id,
                uploaded_files=uploaded_names or None,
                user_id=user_id,
                user_email=user_email,
                message_id=message_id,
            ):
                data = json.loads(event.to_sse().replace("data: ", "").strip())

                if data.get("type") == "text_delta" and data.get("text"):
                    accumulated_text += data["text"]
                elif data.get("type") == "result":
                    turns_used = data.get("turns_used")
                    cost_usd = data.get("cost_usd")
                elif data.get("type") == "error":
                    is_error = True
                    error_msg = data.get("message")

                yield event.to_sse()

        except Exception as e:
            logger.error(f"Stream error for session {session_id}: {e}", exc_info=True)
            is_error = True
            error_msg = str(e)
            yield f'data: {{"type": "error", "message": "Internal stream error: {str(e)}"}}\n\n'
        finally:
            # Update the message document with the agent's response
            await update_message_response(
                message_id=message_id,
                agent_response=accumulated_text or None,
                error=error_msg if is_error else None,
                turns_used=turns_used,
                cost_usd=cost_usd,
            )
            logger.info(f"Stream finished for session {session_id}, message_id={message_id}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
