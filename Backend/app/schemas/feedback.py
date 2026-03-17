from typing import Literal
from pydantic import BaseModel


class FeedbackRequest(BaseModel):
    message_id: str
    conversation_id: str
    sentiment: Literal["liked", "disliked"]
    description: str | None = None


class FeedbackOut(BaseModel):
    feedback_id: str
    message_id: str
    conversation_id: str
    user_email: str
    sentiment: str
    description: str | None
    created_at: str
