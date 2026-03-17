from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_current_user
from app.db.feedback import create_feedback
from app.db.messages import get_message, set_message_like
from app.schemas.message import LikeRequest, MessageOut

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/{message_id}", response_model=MessageOut)
async def get_single_message(
    message_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Fetch a single message/turn by ID."""
    msg = await get_message(message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return MessageOut(**msg)


@router.patch("/{message_id}/like", response_model=MessageOut)
async def like_message(
    message_id: str,
    body: LikeRequest,
    current_user: dict = Depends(get_current_user),
):
    """Set like/dislike/none on a message. Updates messages.is_liked and upserts feedback record."""
    msg = await get_message(message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    # 1. Update the boolean on the message document (source of truth for UI restore)
    await set_message_like(message_id, body.is_liked)

    # 2. Upsert feedback record (audit log / analytics) — skip if reaction is removed
    if body.is_liked is not None:
        sentiment = "liked" if body.is_liked else "disliked"
        await create_feedback(
            message_id=message_id,
            conversation_id=msg["conversation_id"],
            user_id=current_user["user_id"],
            user_email=current_user["email"],
            sentiment=sentiment,
            description=body.description,
        )

    updated = await get_message(message_id)
    return MessageOut(**updated)
