from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.retrieval import HybridSearchEngine
from app.api.deps import get_current_active_user, get_current_workspace, require_scope
from app.core.database import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.common import APIResponse
from app.schemas.search import (
    CrossModalFusionResponse,
    CrossModalSearchRequest,
    DecomposedSearchRequest,
    DecomposedSearchResponse,
    FederatedSearchRequest,
    FederatedSearchResponse,
    HybridSearchRequest,
    HybridSearchResponse,
    SearchResultResponseItem,
)

router = APIRouter(prefix="/search", tags=["Search"])


@router.post("/hybrid", response_model=APIResponse[HybridSearchResponse])
async def hybrid_search(
    data: HybridSearchRequest,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope: None = Depends(require_scope("search")),
):
    results = await HybridSearchEngine.search(
        db=db,
        workspace_id=current_workspace.id,
        query=data.query,
        top_k=data.top_k,
        filter_category=data.filter_category,
        include_documents=data.include_documents,
        include_memories=data.include_memories,
    )

    items = [
        SearchResultResponseItem(
            source_type=r.source_type,
            id=r.id,
            title=r.title,
            content=r.content,
            score=r.score,
            category=r.category,
            section_title=r.section_title,
            metadata=r.metadata,
        )
        for r in results
    ]

    return APIResponse(
        success=True,
        data=HybridSearchResponse(
            query=data.query,
            results=items,
            total_found=len(items),
        ),
    )


@router.post("/federated", response_model=APIResponse[FederatedSearchResponse])
async def federated_search(
    data: FederatedSearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    _scope: None = Depends(require_scope("search")),
):
    """Perform federated cross-workspace retrieval across multiple authorized workspaces."""
    from app.ai.federated_search import FederatedSearchEngine

    result = await FederatedSearchEngine.federated_search(
        db=db,
        user_id=current_user.id,
        request=data,
    )
    return APIResponse(
        success=True,
        data=result,
    )


@router.post("/decomposed", response_model=APIResponse[DecomposedSearchResponse])
async def decomposed_search(
    data: DecomposedSearchRequest,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope: None = Depends(require_scope("search")),
):
    """
    Semantic Query Decomposition & Sub-Query Planning.
    Decomposes complex, comparative, and multi-part queries into atomic sub-queries,
    retrieves aspect-specific evidence in parallel, fuses candidates, and outputs
    a structured multi-aspect contextual briefing.
    """
    from app.ai.query_decomposer import QueryDecompositionEngine

    result = await QueryDecompositionEngine.decompose_and_search(
        db=db,
        workspace_id=current_workspace.id,
        request=data,
    )
    return APIResponse(
        success=True,
        data=result,
    )


@router.post("/cross-modal-fusion", response_model=APIResponse[CrossModalFusionResponse])
async def cross_modal_fusion_search(
    data: CrossModalSearchRequest,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope: None = Depends(require_scope("search")),
):
    """
    Multi-Modal Cross-Attention Memory Fusion & Synesthetic Retrieval Engine.
    Dynamically fuses relevance scores across text, code structures, tabular data, and audio transcripts.
    """
    from app.ai.cross_modal_fusion import CrossModalFusionEngine

    result = await CrossModalFusionEngine.search(
        db=db,
        workspace_id=current_workspace.id,
        request=data,
    )
    return APIResponse(success=True, data=result)
