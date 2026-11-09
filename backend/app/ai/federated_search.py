from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.retrieval import HybridSearchEngine
from app.models.workspace import Workspace, WorkspaceMember
from app.schemas.search import (
    FederatedSearchRequest,
    FederatedSearchResponse,
    FederatedSearchResultItem,
)

logger = logging.getLogger("memoryverse.federated_search")


class FederatedSearchEngine:
    """Multi-workspace federated retrieval engine enforcing cryptographic tenancy isolation."""

    @classmethod
    async def federated_search(
        cls,
        db: AsyncSession,
        user_id: str,
        request: FederatedSearchRequest,
    ) -> FederatedSearchResponse:
        """
        Federate semantic & lexical search across multiple workspaces where the user is an active member.
        Enforces strict authorization: if the user lacks membership in any requested workspace, rejects with 403.
        """
        now_dt = datetime.now(UTC)

        if not request.workspace_ids:
            return FederatedSearchResponse(
                query=request.query,
                total_results=0,
                federated_workspaces_searched=[],
                results=[],
                searched_at=now_dt,
            )

        # 1. Tenancy Authorization & Workspace Name Resolution
        workspace_names: dict[str, str] = {}
        for ws_id in request.workspace_ids:
            q = (
                select(Workspace.id, Workspace.name)
                .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
                .where(
                    Workspace.id == ws_id,
                    WorkspaceMember.user_id == user_id,
                )
            )
            row = (await db.execute(q)).first()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: User is not an authorized member of workspace '{ws_id}'.",
                )
            workspace_names[row[0]] = row[1]

        # 2. Cross-workspace federated retrieval
        federated_items: list[FederatedSearchResultItem] = []

        for ws_id, ws_name in workspace_names.items():
            search_res = await HybridSearchEngine.search(
                db=db,
                workspace_id=ws_id,
                query=request.query,
                top_k=request.top_k_per_workspace,
                include_documents=request.include_documents,
                include_memories=request.include_memories,
            )

            for item in search_res:
                federated_items.append(
                    FederatedSearchResultItem(
                        source_workspace_id=ws_id,
                        source_workspace_name=ws_name,
                        source_type=item.source_type,
                        id=item.id,
                        title=item.title,
                        content=item.content,
                        score=item.score,
                        category=item.category,
                        metadata=item.metadata or {},
                    )
                )

        # 3. Global ranking across federated candidates
        federated_items.sort(key=lambda x: x.score, reverse=True)

        return FederatedSearchResponse(
            query=request.query,
            total_results=len(federated_items),
            federated_workspaces_searched=list(workspace_names.values()),
            results=federated_items,
            searched_at=now_dt,
        )
