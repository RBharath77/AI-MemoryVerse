from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.document import DocumentStatus


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    user_id: str
    title: str
    filename: str
    file_size: int
    mime_type: str
    file_hash: str
    status: DocumentStatus
    error_message: str | None = None
    page_count: int | None = None
    word_count: int | None = None
    token_count: int | None = None
    summary: str | None = None
    extracted_metadata: dict = {}
    chunk_count: int = 0
    created_at: datetime
    updated_at: datetime


class DocumentChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    workspace_id: str
    chunk_index: int
    content: str
    token_count: int
    start_char: int | None = None
    end_char: int | None = None
    section_title: str | None = None
    extra_metadata: dict = {}
    created_at: datetime


class DocumentUploadResponse(BaseModel):
    document: DocumentResponse
    message: str = "Document uploaded successfully and queued for processing."


class DocumentRetryResponse(BaseModel):
    document_id: str
    status: DocumentStatus
    message: str = "Document reprocessing initiated."
