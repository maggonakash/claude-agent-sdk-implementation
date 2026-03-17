from pydantic import BaseModel


class AgentResponse(BaseModel):
    session_id: str
    result: str
    files_modified: list[str]
    session_dir: str


class HistoryEntry(BaseModel):
    role: str
    content: str
    timestamp: str


class SessionInfo(BaseModel):
    session_id: str
    sdk_session_id: str | None = None
    title: str | None = None
    created_at: str
    updated_at: str
    history: list[HistoryEntry]


class SessionSummary(BaseModel):
    session_id: str
    title: str | None = None
    created_at: str
    updated_at: str


class PaginatedSessions(BaseModel):
    sessions: list[SessionSummary]
    total: int
    page: int
    page_size: int
    has_more: bool


class PaginatedHistory(BaseModel):
    history: list[HistoryEntry]
    total: int
    page: int
    page_size: int
    has_more: bool


class FileInfo(BaseModel):
    name: str
    path: str
    size_bytes: int


class NewSessionResponse(BaseModel):
    session_id: str
    session_dir: str


class UpdateSessionRequest(BaseModel):
    title: str
