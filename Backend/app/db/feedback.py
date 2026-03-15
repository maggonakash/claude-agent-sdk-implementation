"""Feedback CRUD operations."""
import uuid
from datetime import datetime, timezone

from app.db.connection import feedback_collection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_indexes():
    await feedback_collection.create_index("feedback_id", unique=True)
    await feedback_collection.create_index("message_id")
    await feedback_collection.create_index("user_id")


async def create_feedback(
    message_id: str,
    conversation_id: str,
    user_id: str,
    user_email: str,
    sentiment: str,  # "liked" | "disliked"
    description: str | None = None,
) -> dict:
    """Upsert feedback — one record per (user_id, message_id). Updates in-place on toggle."""
    now = _now()
    result = await feedback_collection.find_one_and_update(
        {"user_id": user_id, "message_id": message_id},
        {
            "$set": {
                "sentiment": sentiment,
                "description": description,
                "updated_at": now,
            },
            "$setOnInsert": {
                "feedback_id": str(uuid.uuid4()),
                "conversation_id": conversation_id,
                "user_email": user_email,
                "created_at": now,
            },
        },
        upsert=True,
        return_document=True,
    )
    return {k: v for k, v in result.items() if k != "_id"}


async def get_feedback_for_message(message_id: str) -> list[dict]:
    cursor = feedback_collection.find({"message_id": message_id}, {"_id": 0})
    return await cursor.to_list(length=None)


async def get_user_feedback(user_id: str, message_id: str | None = None) -> list[dict]:
    query: dict = {"user_id": user_id}
    if message_id:
        query["message_id"] = message_id
    cursor = feedback_collection.find(query, {"_id": 0}).sort("created_at", -1)
    return await cursor.to_list(length=100)


async def delete_feedback(feedback_id: str, user_id: str) -> bool:
    result = await feedback_collection.delete_one(
        {"feedback_id": feedback_id, "user_id": user_id}
    )
    return result.deleted_count > 0
