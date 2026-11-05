from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.retrieval import HybridSearchEngine
from app.api.deps import get_current_workspace
from app.core.database import get_db
from app.models.workspace import Workspace
from app.schemas.common import APIResponse
from app.schemas.search import (
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
