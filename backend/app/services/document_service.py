import hashlib
import logging
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.chunker import DocumentChunker
from app.ai.document_parser import DocumentParser
from app.core.storage import get_storage_provider
from app.models.document import Document, DocumentChunk, DocumentStatus

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25MB
ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "txt", "md", "markdown", "csv", "json", "html", "htm"}


class DocumentService:
    @staticmethod
    async def upload_document(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        file: UploadFile,
        title: str | None = None,
    ) -> Document:
        filename = file.filename or "untitled_document"
        ext = filename.lower().split(".")[-1] if "." in filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            supported = ", ".join(sorted(ALLOWED_EXTENSIONS))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{ext}'. Supported: {supported}",
            )

        file_bytes = await file.read()
        file_size = len(file_bytes)

        if file_size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File exceeds maximum size of 25MB ({file_size / (1024 * 1024):.2f}MB).",
            )

        file_hash = hashlib.sha256(file_bytes).hexdigest()
        file_key = f"workspaces/{workspace_id}/documents/{uuid.uuid4().hex}_{filename}"

        storage = get_storage_provider()
        await storage.upload_file(
            file_bytes=file_bytes,
            file_key=file_key,
            content_type=file.content_type or "application/octet-stream",
        )

        doc_title = title.strip() if title and title.strip() else filename

        doc = Document(
            workspace_id=workspace_id,
            user_id=user_id,
            title=doc_title,
            filename=filename,
            file_key=file_key,
            file_size=file_size,
            mime_type=file.content_type or "application/octet-stream",
            file_hash=file_hash,
            status=DocumentStatus.PROCESSING,
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        # Execute extraction and chunking pipeline
        await DocumentService.process_document(db, doc.id)
        await db.refresh(doc)
        return doc

    @staticmethod
    async def process_document(db: AsyncSession, document_id: str) -> Document:
        doc = await db.get(Document, document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found.",
            )

        try:
            doc.status = DocumentStatus.EXTRACTING_TEXT
            await db.commit()

            storage = get_storage_provider()
            file_bytes = await storage.download_file(doc.file_key)

            # 1. Parse document text and metadata
            parsed = DocumentParser.parse(
                file_bytes=file_bytes,
                filename=doc.filename,
                mime_type=doc.mime_type,
            )

            doc.page_count = parsed.page_count
            doc.word_count = parsed.word_count
            doc.token_count = parsed.token_count
            doc.summary = parsed.summary
            doc.extracted_metadata = parsed.metadata or {}

            # 2. Chunk document text
            doc.status = DocumentStatus.CHUNKING
            await db.commit()

            chunks = DocumentChunker.auto_chunk(
                text=parsed.text,
                filename=doc.filename,
                mime_type=doc.mime_type,
            )

            # Clear existing chunks if re-processing
            del_q = select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
            existing_chunks = (await db.execute(del_q)).scalars().all()
            for ec in existing_chunks:
                await db.delete(ec)
            await db.flush()

            for chunk_data in chunks:
                chunk_obj = DocumentChunk(
                    document_id=doc.id,
                    workspace_id=doc.workspace_id,
                    chunk_index=chunk_data.chunk_index,
                    content=chunk_data.content,
                    token_count=chunk_data.token_count,
                    start_char=chunk_data.start_char,
                    end_char=chunk_data.end_char,
                    section_title=chunk_data.section_title,
                    extra_metadata=chunk_data.metadata,
                )
                db.add(chunk_obj)

            doc.status = DocumentStatus.COMPLETED
            doc.error_message = None
            await db.commit()
            await db.refresh(doc)
            return doc

        except Exception as e:
            logger.error(f"Failed processing document {document_id}: {e}", exc_info=True)
            doc.status = DocumentStatus.FAILED
            doc.error_message = str(e)
            await db.commit()
            await db.refresh(doc)
            return doc

    @staticmethod
    async def list_documents(
        db: AsyncSession,
        workspace_id: str,
        status_filter: DocumentStatus | None = None,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Document], int]:
        query = select(Document).where(Document.workspace_id == workspace_id)

        if status_filter:
            query = query.where(Document.status == status_filter)
        if search:
            query = query.where(
                or_(
                    Document.title.ilike(f"%{search}%"),
                    Document.filename.ilike(f"%{search}%"),
                )
            )

        count_query = select(func.count(Document.id)).where(Document.workspace_id == workspace_id)
        if status_filter:
            count_query = count_query.where(Document.status == status_filter)
        if search:
            count_query = count_query.where(
                or_(
                    Document.title.ilike(f"%{search}%"),
                    Document.filename.ilike(f"%{search}%"),
                )
            )

        total_res = await db.execute(count_query)
        total = total_res.scalar() or 0

        query = query.order_by(desc(Document.created_at)).limit(limit).offset(offset)
        res = await db.execute(query)
        return list(res.scalars().all()), total

    @staticmethod
    async def get_document(
        db: AsyncSession,
        workspace_id: str,
        document_id: str,
    ) -> Document:
        query = select(Document).where(
            Document.id == document_id,
            Document.workspace_id == workspace_id,
        )
        res = await db.execute(query)
        doc = res.scalar_one_or_none()
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found or unauthorized access.",
            )
        return doc

    @staticmethod
    async def delete_document(
        db: AsyncSession,
        workspace_id: str,
        document_id: str,
    ) -> bool:
        doc = await DocumentService.get_document(db, workspace_id, document_id)
        storage = get_storage_provider()
        await storage.delete_file(doc.file_key)
        await db.delete(doc)
        await db.commit()
        return True

    @staticmethod
    async def list_chunks(
        db: AsyncSession,
        workspace_id: str,
        document_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[DocumentChunk], int]:
        # Validate tenancy
        await DocumentService.get_document(db, workspace_id, document_id)

        query = select(DocumentChunk).where(
            DocumentChunk.document_id == document_id,
            DocumentChunk.workspace_id == workspace_id,
        )

        count_query = select(func.count(DocumentChunk.id)).where(
            DocumentChunk.document_id == document_id,
            DocumentChunk.workspace_id == workspace_id,
        )
        total = (await db.execute(count_query)).scalar() or 0

        query = query.order_by(DocumentChunk.chunk_index).limit(limit).offset(offset)
        chunks = (await db.execute(query)).scalars().all()
        return list(chunks), total

    @staticmethod
    async def retry_document(
        db: AsyncSession,
        workspace_id: str,
        document_id: str,
    ) -> Document:
        doc = await DocumentService.get_document(db, workspace_id, document_id)
        doc.status = DocumentStatus.PENDING
        doc.error_message = None
        await db.commit()

        # Re-trigger processing
        return await DocumentService.process_document(db, doc.id)

    @staticmethod
    async def get_download_url(
        db: AsyncSession,
        workspace_id: str,
        document_id: str,
    ) -> str:
        doc = await DocumentService.get_document(db, workspace_id, document_id)
        storage = get_storage_provider()
        return await storage.get_download_url(doc.file_key)
