from pydantic import BaseModel


class ArtifactOut(BaseModel):
    artifact_id: str
    session_id: str
    message_id: str
    filename: str
    file_path: str
    file_size: int
    mime_type: str
    created_at: str
    updated_at: str


class PaginatedArtifacts(BaseModel):
    artifacts: list[ArtifactOut]
    total: int
    page: int
    page_size: int
    has_more: bool
