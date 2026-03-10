"""
File-based session store.

Each session is stored as a JSON file under workspace/sessions/{session_id}.json.
This maps our application-level session IDs (pre-generated UUIDs) to the SDK's
internal session IDs, and persists conversation history for retrieval on resume.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _sessions_dir(workspace: Path) -> Path:
    d = workspace / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _session_path(workspace: Path, session_id: str) -> Path:
    return _sessions_dir(workspace) / f"{session_id}.json"


def generate_session_id() -> str:
    """Generate a new UUID-based session ID."""
    return str(uuid.uuid4())


def create_session(workspace: Path, session_id: str) -> dict:
    """Create a new session record on disk. Returns the session dict."""
    session = {
        "session_id": session_id,
        "sdk_session_id": None,  # Set after first query()
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "history": [],
    }
    path = _session_path(workspace, session_id)
    path.write_text(json.dumps(session, indent=2))
    logger.info(f"Created session {session_id}")
    return session


def get_session(workspace: Path, session_id: str) -> dict | None:
    """Load a session from disk. Returns None if not found."""
    path = _session_path(workspace, session_id)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def session_exists(workspace: Path, session_id: str) -> bool:
    return _session_path(workspace, session_id).exists()


def update_session(workspace: Path, session_id: str, **fields: Any) -> dict:
    """Update specific fields on an existing session and save."""
    session = get_session(workspace, session_id)
    if session is None:
        raise ValueError(f"Session '{session_id}' not found")
    session.update(fields)
    session["updated_at"] = datetime.now(timezone.utc).isoformat()
    _session_path(workspace, session_id).write_text(json.dumps(session, indent=2))
    return session


def add_history_entry(
    workspace: Path,
    session_id: str,
    role: str,
    content: str,
) -> None:
    """Append a conversation turn to the session history."""
    session = get_session(workspace, session_id)
    if session is None:
        raise ValueError(f"Session '{session_id}' not found")
    session["history"].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    session["updated_at"] = datetime.now(timezone.utc).isoformat()
    _session_path(workspace, session_id).write_text(json.dumps(session, indent=2))


def get_history(workspace: Path, session_id: str) -> list[dict]:
    """Return conversation history for a session, or empty list if not found."""
    session = get_session(workspace, session_id)
    if session is None:
        return []
    return session.get("history", [])
