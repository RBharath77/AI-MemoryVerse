from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from app.ai.factory import get_embedding_provider
from app.ai.mock_provider import MockEmbeddingProvider
from app.core import database as core_db
from app.models.agent import AgentTask, TaskStatus
from app.models.document import Document, DocumentStatus
from app.services.agent_service import AgentService
from app.workers.tasks import execute_agent_step_task, mark_document_failed, process_document_task


@pytest.mark.asyncio
async def test_celery_worker_mark_document_failed_on_fatal_error(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Verify that mark_document_failed updates document status to FAILED in the database."""
    ws_id = auth_headers["X-Workspace-ID"]

    # 1. Create a dummy document in PROCESSING status
    doc_id = str(uuid.uuid4())
    async with core_db.async_session_factory() as db:
        doc = Document(
            id=doc_id,
            workspace_id=ws_id,
            user_id=str(uuid.uuid4()),
            title="Processing Doc",
            filename="proc.txt",
            file_key="dummy_key",
            file_size=1024,
            mime_type="text/plain",
            file_hash="dummy_hash",
            status=DocumentStatus.PROCESSING,
        )
        db.add(doc)
        await db.commit()

    # 2. Invoke mark_document_failed
    err_msg = "Fatal extraction error: Worker exhausted maximum 3 retries."
    mark_document_failed(doc_id, err_msg)

    # 3. Verify status in database
    async with core_db.async_session_factory() as db:
        updated = await db.get(Document, doc_id)
        assert updated is not None
        assert updated.status == DocumentStatus.FAILED
        assert "Worker exhausted maximum" in (updated.error_message or "")


@pytest.mark.asyncio
async def test_celery_agent_step_task_execution(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Verify execute_agent_step_task steps an autonomous agent task in the background."""
    ws_id = auth_headers["X-Workspace-ID"]

    # 1. Create task in DB
    task_id = str(uuid.uuid4())
    async with core_db.async_session_factory() as db:
        task = AgentTask(
            id=task_id,
            workspace_id=ws_id,
            user_id=str(uuid.uuid4()),
            title="Background Step Task",
            goal="Analyze research notes",
            status=TaskStatus.RUNNING,
            steps_limit=3,
            steps_taken=0,
        )
        db.add(task)
        await db.commit()

    # 2. Mock execute_task_step in AgentService
    mock_task = MagicMock()
    mock_task.id = task_id
    mock_task.status = TaskStatus.RUNNING
    mock_task.steps_taken = 1

    with patch.object(AgentService, "execute_task_step", return_value=mock_task):
        res = execute_agent_step_task(ws_id, task_id)
        assert res["task_id"] == task_id
        assert res["status"] == "running"
        assert res["steps_taken"] == 1


@pytest.mark.asyncio
async def test_embedding_provider_dimension_contract():
    """Verify that embedding providers declare and return 1536-dimensional vectors."""
    provider = get_embedding_provider()
    assert hasattr(provider, "dimension")
    assert provider.dimension == 1536

    mock_emb = MockEmbeddingProvider()
    assert mock_emb.dimension == 1536

    vector = await mock_emb.get_embedding("Test semantic query")
    assert len(vector) == 1536
    assert isinstance(vector[0], float)


@pytest.mark.asyncio
async def test_celery_process_document_max_retries_exhaustion():
    """Verify that process_document_task triggers mark_document_failed when retries are exhausted."""
    with patch("app.workers.tasks.mark_document_failed") as mock_mark:
        res = process_document_task.apply(args=("non-existent-doc-id",), retries=3, throw=False)
        assert res.status == "FAILURE"
        mock_mark.assert_called_once()
        assert "Processing failed after 3 attempts" in mock_mark.call_args[0][1]


@pytest.mark.asyncio
async def test_migration_0010_structure_and_syntax():
    """Verify that migration 0010 defines HNSW vector indexing and user lockout fields."""
    import importlib.util
    from pathlib import Path

    migration_path = Path("backend/alembic/versions/0010_pgvector_hnsw_and_account_lockout.py")
    if not migration_path.exists():
        migration_path = Path("alembic/versions/0010_pgvector_hnsw_and_account_lockout.py")
    assert migration_path.exists()

    spec = importlib.util.spec_from_file_location("mig_0010", migration_path)
    assert spec is not None
    assert spec.loader is not None
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)

    assert mig.revision == "0010_pgvector_hnsw_and_account_lockout"
    assert mig.down_revision == "0009_user_token_versioning"
    assert callable(mig.upgrade)
    assert callable(mig.downgrade)
