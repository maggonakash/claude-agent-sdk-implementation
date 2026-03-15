"""User CRUD operations."""
import uuid
from datetime import datetime, timezone
from typing import Any

from app.db.connection import users_collection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_indexes():
    await users_collection.create_index("email", unique=True)
    await users_collection.create_index("user_id", unique=True)


async def create_user(email: str, username: str, password_hash: str) -> dict:
    user = {
        "user_id": str(uuid.uuid4()),
        "email": email.lower().strip(),
        "username": username.strip(),
        "password_hash": password_hash,
        "is_active": True,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await users_collection.insert_one(user)
    return _sanitize(user)


async def get_user_by_email(email: str) -> dict | None:
    doc = await users_collection.find_one({"email": email.lower().strip()})
    return doc  # include password_hash for verification


async def get_user_by_id(user_id: str) -> dict | None:
    doc = await users_collection.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    return doc


async def email_exists(email: str) -> bool:
    count = await users_collection.count_documents({"email": email.lower().strip()}, limit=1)
    return count > 0


def _sanitize(user: dict) -> dict:
    """Return user dict without sensitive fields."""
    return {k: v for k, v in user.items() if k not in ("_id", "password_hash")}
