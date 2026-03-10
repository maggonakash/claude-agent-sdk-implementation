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
        "sdk_session_id": None,  # Set after first query()
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "history": [],
    }

    await sessions_collection.insert_one(session)
    logger.info(f"Created session {session_id} in MongoDB")
    return session

async def get_session(session_id: str) -> dict | None:
    """Load a session from MongoDB. Returns None if not found."""
    # Exclude the internal MongoDB _id from the returned dict
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
    """Return conversation history for a session, or empty list if not found."""
    session = await get_session(session_id)
    if session is None:
        return []
    return session.get("history", [])