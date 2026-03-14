"""
MongoDB-based session store using Motor.

Each session is stored as a document in the 'sessions' collection.
This maps our application-level session IDs (pre-generated UUIDs) to the SDK's
internal session IDs, and persists conversation history for retrieval on resume.
"""

import logging
import uuid
import certifi
from datetime import datetime, timezone
from typing import Any
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings

logger = logging.getLogger(__name__)

# Configure MongoDB connection
client = AsyncIOMotorClient(settings.MONGODB_URI, tlsCAFile=certifi.where())
db = client[settings.MONGODB_DB_NAME]
sessions_collection = db["sessions"]

def generate_session_id() -> str:
    """Generate a new UUID-based session ID."""
    return str(uuid.uuid4())

async def create_session(session_id: str) -> dict:
    """Create a new session record in MongoDB. Returns the session dict."""
    session = {
        "session_id": session_id,
        "sdk_session_id": None,
        "title": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "history": [],
    }

    await sessions_collection.insert_one(session)
    logger.info(f"Created session {session_id} in MongoDB")
    return session

async def soft_delete_session(session_id: str) -> bool:
    """Soft-delete a session by setting is_deleted=True. Returns True if found."""
    result = await sessions_collection.update_one(
        {"session_id": session_id},
        {"$set": {"is_deleted": True, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return result.matched_count > 0

async def set_session_title(session_id: str, title: str) -> None:
    """Set the title for a session (derived from the first user message)."""
    await sessions_collection.update_one(
        {"session_id": session_id},
        {"$set": {"title": title, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )

async def get_session(session_id: str) -> dict | None:
    """Load a session from MongoDB. Returns None if not found."""
    return await sessions_collection.find_one({"session_id": session_id}, {"_id": 0})

async def session_exists(session_id: str) -> bool:
    """Check if a session document exists."""
    count = await sessions_collection.count_documents({"session_id": session_id}, limit=1)
    return count > 0

async def update_session(session_id: str, **fields: Any) -> dict:
    """Update specific fields on an existing session and save."""
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()

    updated_session = await sessions_collection.find_one_and_update(
        {"session_id": session_id},
        {"$set": fields},
        return_document=True,
        projection={"_id": 0}
    )

    if not updated_session:
        raise ValueError(f"Session '{session_id}' not found")
    return updated_session

async def add_history_entry(session_id: str, role: str, content: str) -> None:
    """Append a conversation turn to the session history array in MongoDB."""
    entry = {
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    result = await sessions_collection.update_one(
        {"session_id": session_id},
        {
            "$push": {"history": entry},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
        }
    )

    if result.matched_count == 0:
        raise ValueError(f"Session '{session_id}' not found")

async def get_history(session_id: str) -> list[dict]:
    """Return full conversation history for a session, or empty list if not found."""
    session = await get_session(session_id)
    if session is None:
        return []
    return session.get("history", [])

async def list_sessions_paginated(page: int = 1, page_size: int = 20) -> dict:
    """
    Return a paginated list of sessions sorted by updated_at descending.
    Only returns summary fields (session_id, title, created_at, updated_at).
    """
    query = {"is_deleted": {"$ne": True}}
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

async def get_history_paginated(session_id: str, page: int = 1, page_size: int = 20) -> dict:
    """
    Return a paginated slice of conversation history for a session.
    History is returned in chronological order (oldest first).
    Page 1 returns the most recent page_size entries. Higher pages go further back.
    """
    session = await sessions_collection.find_one(
        {"session_id": session_id},
        {"_id": 0, "history": 1}
    )
    if session is None:
        return {"history": [], "total": 0, "page": page, "page_size": page_size, "has_more": False}

    full_history: list[dict] = session.get("history", [])
    total = len(full_history)

    # Slice from the end so page=1 returns the most recent entries
    end = total - (page - 1) * page_size
    start = max(0, end - page_size)
    sliced = full_history[start:end]

    return {
        "history": sliced,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": start > 0,
    }
