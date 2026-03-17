"""Session CRUD operations (user-scoped)."""
import uuid
from datetime import datetime, timezone

from app.db.connection import sessions_collection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_indexes():
    await sessions_collection.create_index("session_id", unique=True)
    await sessions_collection.create_index("user_id")
    await sessions_collection.create_index("user_email")


def generate_session_id() -> str:
    return str(uuid.uuid4())


async def create_session(session_id: str, user_id: str, user_email: str) -> dict:
    session = {
        "session_id": session_id,
        "user_id": user_id,
        "user_email": user_email,
        "sdk_session_id": None,
        "title": None,
        "is_deleted": False,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await sessions_collection.insert_one(session)
    return session


async def get_session(session_id: str) -> dict | None:
    return await sessions_collection.find_one(
        {"session_id": session_id},
        {"_id": 0}
    )


async def session_exists(session_id: str) -> bool:
    count = await sessions_collection.count_documents(
        {"session_id": session_id, "is_deleted": {"$ne": True}},
        limit=1,
    )
    return count > 0


async def session_belongs_to_user(session_id: str, user_id: str) -> bool:
    count = await sessions_collection.count_documents(
        {"session_id": session_id, "user_id": user_id, "is_deleted": {"$ne": True}},
        limit=1
    )
    return count > 0


async def set_session_title(session_id: str, title: str) -> None:
    await sessions_collection.update_one(
        {"session_id": session_id},
        {"$set": {"title": title, "updated_at": _now()}},
    )


async def update_session(session_id: str, **fields) -> dict:
    fields["updated_at"] = _now()
    doc = await sessions_collection.find_one_and_update(
        {"session_id": session_id},
        {"$set": fields},
        return_document=True,
        projection={"_id": 0},
    )
    if not doc:
        raise ValueError(f"Session '{session_id}' not found")
    return doc


async def soft_delete_session(session_id: str) -> bool:
    result = await sessions_collection.update_one(
        {"session_id": session_id},
        {"$set": {"is_deleted": True, "updated_at": _now()}},
    )
    return result.matched_count > 0


async def list_sessions_paginated(user_id: str, page: int = 1, page_size: int = 20) -> dict:
    query = {"user_id": user_id, "is_deleted": {"$ne": True}}
    skip = (page - 1) * page_size
    total = await sessions_collection.count_documents(query)

    cursor = sessions_collection.find(
        query,
        {"_id": 0, "session_id": 1, "title": 1, "created_at": 1, "updated_at": 1}
    ).sort("updated_at", -1).skip(skip).limit(page_size)

    sessions = await cursor.to_list(length=page_size)
    return {
        "sessions": sessions,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": (skip + len(sessions)) < total,
    }
