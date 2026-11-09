from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_active_user,
    get_current_workspace,
    require_scope,
)
from app.core.database import get_db
from app.core.storage import get_storage_provider
from app.models.document import Document, DocumentStatus
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.schemas.common import APIResponse, PaginatedResponse
from app.schemas.document import (
    DocumentChunkResponse,
    DocumentResponse,
    DocumentRetryResponse,
    DocumentUploadResponse,
    ExtractedTableData,
    SchemaExtractionRequest,
    SchemaExtractionResponse,
    TableParseRequest,
    TableParseResponse,
)
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get("", response_model=APIResponse[PaginatedResponse[DocumentResponse]])
async def list_documents(
    status_filter: DocumentStatus | None = Query(default=None, alias="status"),
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope: None = Depends(require_scope("documents:read")),
):
    offset = (page - 1) * page_size
    items, total = await DocumentService.list_documents(
        db=db,
        workspace_id=current_workspace.id,
        status_filter=status_filter,
        search=search,
        limit=page_size,
        offset=offset,
    )
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    return APIResponse(
        success=True,
        data=PaginatedResponse(
            items=[
                DocumentResponse(
                    id=doc.id,
                    workspace_id=doc.workspace_id,
                    user_id=doc.user_id,
                    title=doc.title,
                    filename=doc.filename,
                    file_size=doc.file_size,
                    mime_type=doc.mime_type,
                    file_hash=doc.file_hash,
                    status=doc.status,
                    error_message=doc.error_message,
                    page_count=doc.page_count,
                    word_count=doc.word_count,
                    token_count=doc.token_count,
                    summary=doc.summary,
                    extracted_metadata=doc.extracted_metadata or {},
                    chunk_count=len(doc.chunks) if doc.chunks is not None else 0,
                    created_at=doc.created_at,
                    updated_at=doc.updated_at,
                )
                for doc in items
            ],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ),
    )


@router.post(
    "/upload",
    response_model=APIResponse[DocumentUploadResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope: None = Depends(require_scope("documents:write")),
):
    doc = await DocumentService.upload_document(
        db=db,
        workspace_id=current_workspace.id,
        user_id=current_user.id,
        file=file,
        title=title,
    )

    doc_resp = DocumentResponse(
        id=doc.id,
        workspace_id=doc.workspace_id,
        user_id=doc.user_id,
        title=doc.title,
        filename=doc.filename,
        file_size=doc.file_size,
        mime_type=doc.mime_type,
        file_hash=doc.file_hash,
        status=doc.status,
        error_message=doc.error_message,
        page_count=doc.page_count,
        word_count=doc.word_count,
        token_count=doc.token_count,
        summary=doc.summary,
        extracted_metadata=doc.extracted_metadata or {},
        chunk_count=len(doc.chunks) if doc.chunks is not None else 0,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )

    return APIResponse(
        success=True,
        data=DocumentUploadResponse(
            document=doc_resp,
            message="Document uploaded and processed successfully.",
        ),
    )


@router.get("/download-file")
async def download_file_by_key(
    key: str = Query(..., description="Storage key of the file to download"),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Secure direct download endpoint resolving file key with multi-tenant tenancy verification."""
    query = select(Document).where(
        Document.file_key == key,
        Document.workspace_id == current_workspace.id,
    )
    doc = (await db.execute(query)).scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File key not found or access denied in this workspace.",
        )

    storage = get_storage_provider()
    try:
        content = await storage.download_file(key)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Physical file not found on storage backend.",
        )

    return Response(
        content=content,
        media_type=doc.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{doc.filename}"',
            "Content-Length": str(len(content)),
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


@router.post(
    "/parse-tables",
    response_model=APIResponse[TableParseResponse],
)
async def parse_document_tables(
    data: TableParseRequest,
    current_workspace: Workspace = Depends(get_current_workspace),
    _scope: None = Depends(require_scope("documents:read")),
):
    """Extract structured tables and header-preserving tabular chunks from document markdown or CSV."""
    from datetime import UTC, datetime

    from app.ai.table_extractor import StructuredTableExtractor

    tables = StructuredTableExtractor.extract_all_tables(
        text=data.content,
        rows_per_chunk=data.rows_per_chunk,
    )

    table_data = [
        ExtractedTableData(
            table_id=t.table_id,
            columns=t.columns,
            row_count=t.row_count,
            records=t.structured_records,
            chunks=[
                {
                    "chunk_index": c.chunk_index,
                    "content": c.content,
                    "token_count": c.token_count,
                    "row_range": list(c.row_range),
                    "metadata": c.metadata,
                }
                for c in t.chunks
            ],
            caption=t.caption,
        )
        for t in tables
    ]

    return APIResponse(
        success=True,
        data=TableParseResponse(
            total_tables_detected=len(table_data),
            tables=table_data,
            parsed_at=datetime.now(UTC),
        ),
    )


@router.post(
    "/extract-schema",
    response_model=APIResponse[SchemaExtractionResponse],
)
async def extract_document_schema(
    data: SchemaExtractionRequest,
    current_workspace: Workspace = Depends(get_current_workspace),
    _scope: None = Depends(require_scope("documents:read")),
):
    """Extract structured, typed JSON data from unstructured document content conforming to a target JSON Schema."""
    from app.ai.schema_extractor import CognitiveSchemaEngine

    result = CognitiveSchemaEngine.extract_structured_schema(
        content=data.content,
        schema=data.schema_definition,
    )
    return APIResponse(
        success=True,
        data=result,
    )


@router.get("/{document_id}", response_model=APIResponse[DocumentResponse])
async def get_document(
    document_id: str,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope: None = Depends(require_scope("documents:read")),
):
    doc = await DocumentService.get_document(db, current_workspace.id, document_id)
    doc_resp = DocumentResponse(
        id=doc.id,
        workspace_id=doc.workspace_id,
        user_id=doc.user_id,
        title=doc.title,
        filename=doc.filename,
        file_size=doc.file_size,
        mime_type=doc.mime_type,
        file_hash=doc.file_hash,
        status=doc.status,
        error_message=doc.error_message,
        page_count=doc.page_count,
        word_count=doc.word_count,
        token_count=doc.token_count,
        summary=doc.summary,
        extracted_metadata=doc.extracted_metadata or {},
        chunk_count=len(doc.chunks) if doc.chunks is not None else 0,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )
    return APIResponse(
        success=True,
        data=doc_resp,
    )


@router.delete("/{document_id}", response_model=APIResponse[dict])
async def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope: None = Depends(require_scope("documents:write")),
):
    is_admin_or_owner = current_user.is_superuser
    if not is_admin_or_owner:
        q = select(WorkspaceMember.role).where(
            WorkspaceMember.workspace_id == current_workspace.id,
            WorkspaceMember.user_id == current_user.id,
        )
        role = (await db.execute(q)).scalar_one_or_none()
        is_admin_or_owner = role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)

    await DocumentService.delete_document(
        db=db,
        workspace_id=current_workspace.id,
        document_id=document_id,
        current_user_id=current_user.id,
        is_admin_or_owner=is_admin_or_owner,
    )
    return APIResponse(
        success=True,
        data={"message": "Document and all extracted chunks deleted successfully."},
    )


@router.get(
    "/{document_id}/chunks", response_model=APIResponse[PaginatedResponse[DocumentChunkResponse]]
)
async def list_document_chunks(
    document_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size
    chunks, total = await DocumentService.list_chunks(
        db=db,
        workspace_id=current_workspace.id,
        document_id=document_id,
        limit=page_size,
        offset=offset,
    )
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    return APIResponse(
        success=True,
        data=PaginatedResponse(
            items=[DocumentChunkResponse.model_validate(c) for c in chunks],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ),
    )


@router.post("/{document_id}/retry", response_model=APIResponse[DocumentRetryResponse])
async def retry_document(
    document_id: str,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    doc = await DocumentService.retry_document(db, current_workspace.id, document_id)
    return APIResponse(
        success=True,
        data=DocumentRetryResponse(
            document_id=doc.id,
            status=doc.status,
            message="Document re-processed successfully.",
        ),
    )


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve temporary or direct download URL for document."""
    url = await DocumentService.get_download_url(db, current_workspace.id, document_id)
    return APIResponse(
        success=True,
        data={"download_url": url},
    )


@router.get("/{document_id}/raw")
async def download_document_raw(
    document_id: str,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Direct stream download for document binary."""
    doc = await DocumentService.get_document(db, current_workspace.id, document_id)
    storage = get_storage_provider()
    try:
        content = await storage.download_file(doc.file_key)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Physical file not found on storage backend.",
        )

    return Response(
        content=content,
        media_type=doc.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{doc.filename}"',
            "Content-Length": str(len(content)),
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )
