"""Message CRUD operations — one document per conversation turn."""
import uuid
from datetime import datetime, timezone

from app.db.connection import messages_collection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_indexes():
    await messages_collection.create_index("message_id", unique=True)
    await messages_collection.create_index("conversation_id")
    await messages_collection.create_index("user_id")
    await messages_collection.create_index("user_email")


async def create_message(
    conversation_id: str,
    user_id: str,
    user_email: str,
    user_message: str,
    files_uploaded: list[str] | None = None,
) -> dict:
    """Create a new turn document when the user sends a message."""
    doc = {
        "message_id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "user_id": user_id,
        "user_email": user_email,
        "user_message": user_message,
        "agent_response": None,
        "error": None,
        "files_uploaded": files_uploaded or [],
        "is_liked": None,
        "turns_used": None,
        "cost_usd": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await messages_collection.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


async def update_message_response(
    message_id: str,
    agent_response: str | None = None,
    error: str | None = None,
    turns_used: int | None = None,
    cost_usd: float | None = None,
) -> None:
    """Update the turn document with the agent response after streaming completes."""
    await messages_collection.update_one(
        {"message_id": message_id},
        {"$set": {
            "agent_response": agent_response,
            "error": error,
            "turns_used": turns_used,
            "cost_usd": cost_usd,
            "updated_at": _now(),
        }},
    )


async def set_message_like(message_id: str, is_liked: bool | None) -> None:
    await messages_collection.update_one(
        {"message_id": message_id},
        {"$set": {"is_liked": is_liked, "updated_at": _now()}},
    )


async def get_message(message_id: str) -> dict | None:
    return await messages_collection.find_one({"message_id": message_id}, {"_id": 0})


async def get_messages_paginated(
    conversation_id: str,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    Return paginated messages for a conversation.
    Page 1 = most recent page_size messages. Higher pages go further back.
    """
    query = {"conversation_id": conversation_id}
    total = await messages_collection.count_documents(query)
    skip = (page - 1) * page_size

    # Sort ascending by created_at, then slice from the end for newest-first pagination
    all_cursor = messages_collection.find(query, {"_id": 0}).sort("created_at", 1)
    all_docs = await all_cursor.to_list(length=None)

    end = total - (page - 1) * page_size
    start = max(0, end - page_size)
    sliced = all_docs[start:end]

    return {
        "messages": sliced,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": start > 0,
    }
