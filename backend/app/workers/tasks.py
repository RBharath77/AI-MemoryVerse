import asyncio
import logging

from app.core.database import async_session_factory
from app.services.document_service import DocumentService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.process_document_task", bind=True, max_retries=3)
def process_document_task(self, document_id: str) -> dict:
    """Asynchronous background worker task to parse, chunk, and index a document."""
    logger.info(f"Starting Celery background processing for document: {document_id}")

    async def _async_run():
        async with async_session_factory() as session:
            doc = await DocumentService.process_document(session, document_id)
            return {"document_id": doc.id, "status": doc.status.value}

    try:
        return asyncio.run(_async_run())
    except Exception as exc:
        logger.error(f"Celery processing failed for document {document_id}: {exc}")
        raise self.retry(exc=exc, countdown=10)
