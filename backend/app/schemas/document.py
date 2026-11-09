from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

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


class TableParseRequest(BaseModel):
    content: str = Field(
        min_length=1, max_length=200000, description="Raw document markdown or CSV text to parse"
    )
    rows_per_chunk: int = Field(
        default=10, ge=1, le=100, description="Number of table rows per contextual chunk"
    )


class ExtractedTableData(BaseModel):
    table_id: str
    columns: list[str]
    row_count: int
    records: list[dict[str, str]]
    chunks: list[dict[str, Any]]
    caption: str | None = None


class TableParseResponse(BaseModel):
    total_tables_detected: int
    tables: list[ExtractedTableData]
    parsed_at: datetime


class TargetJsonSchema(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=1000)
    type: str = "object"
    properties: dict[str, Any] = Field(
        description="JSON Schema property definitions mapping field names to type and metadata"
    )
    required: list[str] = Field(default_factory=list)


class SchemaExtractionRequest(BaseModel):
    content: str = Field(
        min_length=1,
        max_length=100000,
        description="Unstructured document or memory text to extract structured schema fields from",
    )
    schema_definition: TargetJsonSchema


class SchemaExtractionResponse(BaseModel):
    title: str
    is_valid: bool
    extracted_data: dict[str, Any]
    validation_errors: list[str] = Field(default_factory=list)
    extracted_fields_count: int
    extracted_at: datetime
