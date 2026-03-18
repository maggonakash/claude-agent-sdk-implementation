import logging
import mimetypes
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.agent import get_session_paths
from app.core.dependencies import get_current_user
from app.db.artifacts import get_artifact, get_artifacts_by_session
from app.db.sessions import session_belongs_to_user, session_exists
from app.schemas.artifact import ArtifactOut, PaginatedArtifacts

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions/{session_id}/artifacts", tags=["artifacts"])


async def _assert_session_access(session_id: str, user_id: str):
    if not await session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    if not await session_belongs_to_user(session_id, user_id):
        raise HTTPException(status_code=403, detail="Access denied")


def _get_artifact_disk_path(session_id: str, file_path: str) -> Path:
    """Resolve an artifact's file_path to its absolute location on disk."""
    _, _, _, artifacts_dir = get_session_paths(session_id)
    full_path = (artifacts_dir / file_path).resolve()
    # Safety: ensure resolved path is still inside artifacts_dir
    if not str(full_path).startswith(str(artifacts_dir.resolve())):
        raise HTTPException(status_code=400, detail="Invalid file path")
    return full_path


@router.get("", response_model=PaginatedArtifacts)
async def list_artifacts(
    session_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """Return paginated artifacts for a session."""
    await _assert_session_access(session_id, current_user["user_id"])
    result = await get_artifacts_by_session(session_id, page=page, page_size=page_size)
    return PaginatedArtifacts(
        artifacts=[ArtifactOut(**a) for a in result["artifacts"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        has_more=result["has_more"],
    )


@router.get("/{artifact_id}/download")
async def download_artifact(
    session_id: str,
    artifact_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Download an artifact file."""
    await _assert_session_access(session_id, current_user["user_id"])

    artifact = await get_artifact(artifact_id)
    if not artifact or artifact["session_id"] != session_id:
        raise HTTPException(status_code=404, detail="Artifact not found")

    file_path = _get_artifact_disk_path(session_id, artifact["file_path"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Artifact file not found on disk")

    mime_type = artifact.get("mime_type", "application/octet-stream")

    async def _stream_file():
        async with aiofiles.open(file_path, "rb") as f:
            while chunk := await f.read(64 * 1024):
                yield chunk

    return StreamingResponse(
        _stream_file(),
        media_type=mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{artifact["filename"]}"',
            "Content-Length": str(artifact["file_size"]),
        },
    )


@router.get("/{artifact_id}/preview")
async def preview_artifact(
    session_id: str,
    artifact_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Serve an artifact file inline for preview.

    Returns the raw file with Content-Disposition: inline so the browser
    or frontend library (react-pdf, docx-preview, etc.) can render it.
    """
    await _assert_session_access(session_id, current_user["user_id"])

    artifact = await get_artifact(artifact_id)
    if not artifact or artifact["session_id"] != session_id:
        raise HTTPException(status_code=404, detail="Artifact not found")

    file_path = _get_artifact_disk_path(session_id, artifact["file_path"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Artifact file not found on disk")

    mime_type = artifact.get("mime_type", "application/octet-stream")

    async def _stream_file():
        async with aiofiles.open(file_path, "rb") as f:
            while chunk := await f.read(64 * 1024):
                yield chunk

    return StreamingResponse(
        _stream_file(),
        media_type=mime_type,
        headers={
            "Content-Disposition": f'inline; filename="{artifact["filename"]}"',
            "Content-Length": str(artifact["file_size"]),
        },
    )
