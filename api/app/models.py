from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str


class DocumentCreateRequest(BaseModel):
    filename: str
    content_type: str
    size_bytes: int = Field(gt=0)
    sha256: str


class DocumentCreateResponse(BaseModel):
    id: str
    status: str
    created_at: datetime
    is_duplicate: bool = False


class DocumentProcessResponse(BaseModel):
    document_id: str
    status: str
    chunk_count: int


class DocumentSummary(BaseModel):
    id: str
    filename: str
    content_type: Optional[str] = None
    status: str
    size_bytes: int
    created_at: datetime


class ChatAskRequest(BaseModel):
    chat_id: Optional[str] = None
    document_id: Optional[str] = None
    question: str = Field(min_length=3)


class Citation(BaseModel):
    document_id: str
    document_name: str
    page: int
    section: Optional[str] = None
    snippet: str


class ChatAskResponse(BaseModel):
    chat_id: str
    answer: str
    citations: list[Citation]


class ChatMessage(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime


class ChatDetailResponse(BaseModel):
    chat_id: str
    title: Optional[str] = None
    created_at: datetime
    messages: list[ChatMessage]


class ChatSummary(BaseModel):
    chat_id: str
    title: Optional[str] = None
    created_at: datetime
    message_count: int


class JobResponse(BaseModel):
    job_id: str
    status: str
    created_at: datetime


class JobDetailResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    error: Optional[str] = None
    attempts: int
    max_attempts: int
    next_run_at: Optional[datetime] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class AdminMetricsResponse(BaseModel):
    total_users: int
    total_documents: int
    queries_last_24h: int
    jobs_failed_last_24h: int