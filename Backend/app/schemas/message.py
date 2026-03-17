from pydantic import BaseModel


class MessageOut(BaseModel):
    message_id: str
    conversation_id: str
    user_message: str
    agent_response: str | None
    error: str | None
    files_uploaded: list[str]
    is_liked: bool | None
    turns_used: int | None
    cost_usd: float | None
    created_at: str
    updated_at: str


class PaginatedMessages(BaseModel):
    messages: list[MessageOut]
    total: int
    page: int
    page_size: int
    has_more: bool


class LikeRequest(BaseModel):
    is_liked: bool | None  # True=liked, False=disliked, None=remove reaction
    description: str | None = None
