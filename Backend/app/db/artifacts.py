"""Artifact CRUD operations — tracks files created by the agent in ./artifacts/."""
import mimetypes
import uuid
from datetime import datetime, timezone

from app.db.connection import artifacts_collection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _guess_mime(filename: str) -> str:
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"


async def create_indexes():
    await artifacts_collection.create_index("artifact_id", unique=True)
    await artifacts_collection.create_index("session_id")
    await artifacts_collection.create_index("message_id")


async def create_artifact(
    session_id: str,
    message_id: str,
    user_id: str,
    filename: str,
    file_path: str,
    file_size: int,
    mime_type: str | None = None,
) -> dict:
    doc = {
        "artifact_id": str(uuid.uuid4()),
        "session_id": session_id,
        "message_id": message_id,
        "user_id": user_id,
        "filename": filename,
        "file_path": file_path,
        "file_size": file_size,
        "mime_type": mime_type or _guess_mime(filename),
        "created_at": _now(),
        "updated_at": _now(),
    }
    await artifacts_collection.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


async def get_artifact(artifact_id: str) -> dict | None:
    return await artifacts_collection.find_one(
        {"artifact_id": artifact_id}, {"_id": 0}
    )


async def get_artifacts_by_session(
    session_id: str,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    query = {"session_id": session_id}
    total = await artifacts_collection.count_documents(query)
    skip = (page - 1) * page_size

    cursor = (
        artifacts_collection.find(query, {"_id": 0})
        .sort("created_at", 1)
        .skip(skip)
        .limit(page_size)
    )
    docs = await cursor.to_list(length=page_size)

    return {
        "artifacts": docs,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": skip + page_size < total,
    }


async def get_artifacts_by_message(message_id: str) -> list[dict]:
    cursor = artifacts_collection.find(
        {"message_id": message_id}, {"_id": 0}
    ).sort("created_at", 1)
    return await cursor.to_list(length=None)


async def get_artifacts_by_messages(message_ids: list[str]) -> dict[str, list[dict]]:
    """Batch-fetch artifacts for multiple messages. Returns {message_id: [artifacts]}."""
    if not message_ids:
        return {}
    cursor = artifacts_collection.find(
        {"message_id": {"$in": message_ids}}, {"_id": 0}
    ).sort("created_at", 1)
    docs = await cursor.to_list(length=None)

    result: dict[str, list[dict]] = {mid: [] for mid in message_ids}
    for doc in docs:
        mid = doc["message_id"]
        if mid in result:
            result[mid].append(doc)
    return result


async def get_existing_file_paths(session_id: str) -> set[str]:
    """Return set of file_path values already tracked for a session."""
    cursor = artifacts_collection.find(
        {"session_id": session_id}, {"file_path": 1, "_id": 0}
    )
    docs = await cursor.to_list(length=None)
    return {d["file_path"] for d in docs}


async def delete_artifacts_by_session(session_id: str) -> int:
    result = await artifacts_collection.delete_many({"session_id": session_id})
    return result.deleted_count
