import asyncio
import concurrent.futures
import logging
from collections.abc import Coroutine
from typing import Any

from app.core.database import async_session_factory
from app.models.document import Document, DocumentStatus
from app.services.agent_service import AgentService
from app.services.document_service import DocumentService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """Safely execute an async coroutine from either a sync Celery worker or an active event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


def mark_document_failed(document_id: str, error_message: str) -> None:
    """Invoke async database update to mark an orphaned document as FAILED."""

    async def _fail():
        async with async_session_factory() as session:
            doc = await session.get(Document, document_id)
            if doc:
                doc.status = DocumentStatus.FAILED
                doc.error_message = error_message[:1000]
                await session.commit()

    try:
        run_async(_fail())
    except Exception as e:
        logger.error(f"Failed to record document failure for {document_id}: {e}")


@celery_app.task(name="tasks.process_document_task", bind=True, max_retries=3)
def process_document_task(self, document_id: str) -> dict:
    """Asynchronous background worker task to parse, chunk, and index a document."""
    logger.info(f"Starting Celery background processing for document: {document_id}")

    async def _async_run():
        async with async_session_factory() as session:
            doc = await DocumentService.process_document(session, document_id)
            return {"document_id": doc.id, "status": doc.status.value}

    try:
        return run_async(_async_run())
    except Exception as exc:
        logger.error(f"Celery processing failed for document {document_id}: {exc}")
        if getattr(self.request, "retries", 0) >= self.max_retries:
            logger.error(
                f"Max retries ({self.max_retries}) exceeded for document {document_id}. "
                "Marking document status as FAILED."
            )
            mark_document_failed(
                document_id, f"Processing failed after {self.max_retries} attempts: {str(exc)}"
            )
            raise exc
        raise self.retry(exc=exc, countdown=10)


@celery_app.task(name="tasks.execute_agent_step_task", bind=True, max_retries=2)
def execute_agent_step_task(self, workspace_id: str, task_id: str) -> dict:
    """Asynchronous background worker task to execute an autonomous agent step."""
    logger.info(f"Starting Celery background execution for agent task: {task_id}")

    async def _async_step():
        async with async_session_factory() as session:
            task = await AgentService.execute_task_step(session, workspace_id, task_id)
            return {
                "task_id": task.id,
                "status": task.status.value,
                "steps_taken": task.steps_taken,
            }

    try:
        return run_async(_async_step())
    except Exception as exc:
        logger.error(f"Agent step execution failed for task {task_id}: {exc}")
        raise self.retry(exc=exc, countdown=5)
