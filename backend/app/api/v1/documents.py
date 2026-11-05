from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_current_workspace
from app.core.database import get_db
from app.models.document import DocumentStatus
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.common import APIResponse, PaginatedResponse
from app.schemas.document import (
    DocumentChunkResponse,
    DocumentResponse,
    DocumentRetryResponse,
    DocumentUploadResponse,
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


@router.get("/{document_id}", response_model=APIResponse[DocumentResponse])
async def get_document(
    document_id: str,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
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
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    await DocumentService.delete_document(db, current_workspace.id, document_id)
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
    url = await DocumentService.get_download_url(db, current_workspace.id, document_id)
    return APIResponse(
        success=True,
        data={"download_url": url},
    )
