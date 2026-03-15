from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.dependencies import get_current_user
from app.db.feedback import (
    create_feedback,
    delete_feedback,
    get_feedback_for_message,
    get_user_feedback,
)
from app.schemas.feedback import FeedbackOut, FeedbackRequest

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackOut, status_code=201)
async def submit_feedback(
    body: FeedbackRequest,
    current_user: dict = Depends(get_current_user),
):
    """Submit feedback (liked/disliked) on a message."""
    doc = await create_feedback(
        message_id=body.message_id,
        conversation_id=body.conversation_id,
        user_id=current_user["user_id"],
        user_email=current_user["email"],
        sentiment=body.sentiment,
        description=body.description,
    )
    return FeedbackOut(**doc)


@router.get("", response_model=list[FeedbackOut])
async def list_feedback(
    message_id: str | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
):
    """List feedback submitted by the current user, optionally filtered by message."""
    docs = await get_user_feedback(current_user["user_id"], message_id=message_id)
    return [FeedbackOut(**d) for d in docs]


@router.delete("/{feedback_id}", status_code=200)
async def remove_feedback(
    feedback_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a feedback entry (only owner can delete)."""
    deleted = await delete_feedback(feedback_id, current_user["user_id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Feedback not found or access denied")
    return {"status": "deleted", "feedback_id": feedback_id}
