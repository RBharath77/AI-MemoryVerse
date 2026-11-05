from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_workspace
from app.core.database import get_db
from app.models.graph import EntityType
from app.models.workspace import Workspace
from app.schemas.common import APIResponse, PaginatedResponse
from app.schemas.graph import (
    EntityCreate,
    EntityResponse,
    EntityUpdate,
    GraphAnalyticsResponse,
    GraphDataResponse,
    GraphExtractionRequest,
    GraphExtractionResponse,
    RelationshipCreate,
    RelationshipResponse,
)
from app.services.graph_service import GraphService

router = APIRouter(prefix="/graph", tags=["Knowledge Graph"])


@router.get("", response_model=APIResponse[GraphDataResponse])
async def get_workspace_graph(
    limit: int = Query(default=250, ge=1, le=1000),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    graph = await GraphService.get_workspace_graph(
        db=db,
        workspace_id=current_workspace.id,
        limit_nodes=limit,
    )
    return APIResponse(success=True, data=graph)


@router.get("/analytics", response_model=APIResponse[GraphAnalyticsResponse])
async def get_graph_analytics(
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    analytics = await GraphService.get_analytics(
        db=db,
        workspace_id=current_workspace.id,
    )
    return APIResponse(success=True, data=analytics)


@router.get("/entities", response_model=APIResponse[PaginatedResponse[EntityResponse]])
async def list_entities(
    entity_type: EntityType | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size
    items, total = await GraphService.list_entities(
        db=db,
        workspace_id=current_workspace.id,
        entity_type=entity_type,
        search=search,
        limit=page_size,
        offset=offset,
    )
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    return APIResponse(
        success=True,
        data=PaginatedResponse(
            items=[
                EntityResponse(
                    id=e.id,
                    workspace_id=e.workspace_id,
                    name=e.name,
                    entity_type=e.entity_type,
                    description=e.description,
                    mention_count=e.mention_count,
                    degree=deg,
                    extra_metadata=e.extra_metadata or {},
                    created_at=e.created_at,
                    updated_at=e.updated_at,
                )
                for e, deg in items
            ],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ),
    )


@router.post(
    "/entities",
    response_model=APIResponse[EntityResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_entity(
    data: EntityCreate,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    entity = await GraphService.create_entity(
        db=db,
        workspace_id=current_workspace.id,
        data=data,
    )
    return APIResponse(
        success=True,
        data=EntityResponse(
            id=entity.id,
            workspace_id=entity.workspace_id,
            name=entity.name,
            entity_type=entity.entity_type,
            description=entity.description,
            mention_count=entity.mention_count,
            degree=0,
            extra_metadata=entity.extra_metadata or {},
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        ),
    )


@router.get("/entities/{entity_id}", response_model=APIResponse[EntityResponse])
async def get_entity(
    entity_id: str,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    entity, degree = await GraphService.get_entity(
        db=db,
        workspace_id=current_workspace.id,
        entity_id=entity_id,
    )
    return APIResponse(
        success=True,
        data=EntityResponse(
            id=entity.id,
            workspace_id=entity.workspace_id,
            name=entity.name,
            entity_type=entity.entity_type,
            description=entity.description,
            mention_count=entity.mention_count,
            degree=degree,
            extra_metadata=entity.extra_metadata or {},
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        ),
    )


@router.patch("/entities/{entity_id}", response_model=APIResponse[EntityResponse])
async def update_entity(
    entity_id: str,
    data: EntityUpdate,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    entity = await GraphService.update_entity(
        db=db,
        workspace_id=current_workspace.id,
        entity_id=entity_id,
        data=data,
    )
    _, degree = await GraphService.get_entity(db, current_workspace.id, entity.id)
    return APIResponse(
        success=True,
        data=EntityResponse(
            id=entity.id,
            workspace_id=entity.workspace_id,
            name=entity.name,
            entity_type=entity.entity_type,
            description=entity.description,
            mention_count=entity.mention_count,
            degree=degree,
            extra_metadata=entity.extra_metadata or {},
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        ),
    )


@router.delete("/entities/{entity_id}", response_model=APIResponse[dict])
async def delete_entity(
    entity_id: str,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    await GraphService.delete_entity(
        db=db,
        workspace_id=current_workspace.id,
        entity_id=entity_id,
    )
    return APIResponse(
        success=True,
        data={"message": "Entity and associated relationships deleted successfully."},
    )


@router.post(
    "/relationships",
    response_model=APIResponse[RelationshipResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_relationship(
    data: RelationshipCreate,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    rel = await GraphService.create_relationship(
        db=db,
        workspace_id=current_workspace.id,
        data=data,
    )
    return APIResponse(
        success=True,
        data=RelationshipResponse(
            id=rel.id,
            workspace_id=rel.workspace_id,
            source_entity_id=rel.source_entity_id,
            target_entity_id=rel.target_entity_id,
            source_entity_name=rel.source_entity.name if rel.source_entity else None,
            target_entity_name=rel.target_entity.name if rel.target_entity else None,
            relationship_type=rel.relationship_type,
            weight=rel.weight,
            source_memory_id=rel.source_memory_id,
            source_document_id=rel.source_document_id,
            created_at=rel.created_at,
        ),
    )


@router.delete("/relationships/{relationship_id}", response_model=APIResponse[dict])
async def delete_relationship(
    relationship_id: str,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    await GraphService.delete_relationship(
        db=db,
        workspace_id=current_workspace.id,
        relationship_id=relationship_id,
    )
    return APIResponse(
        success=True,
        data={"message": "Relationship deleted successfully."},
    )


@router.get("/neighborhood/{entity_id}", response_model=APIResponse[GraphDataResponse])
async def get_neighborhood(
    entity_id: str,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    neighborhood = await GraphService.get_neighborhood(
        db=db,
        workspace_id=current_workspace.id,
        entity_id=entity_id,
    )
    return APIResponse(success=True, data=neighborhood)


@router.post("/extract", response_model=APIResponse[GraphExtractionResponse])
async def extract_graph(
    data: GraphExtractionRequest,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    e_count, r_count, entities = await GraphService.extract_and_ingest(
        db=db,
        workspace_id=current_workspace.id,
        text=data.text,
        source_memory_id=data.source_memory_id,
        source_document_id=data.source_document_id,
    )
    return APIResponse(
        success=True,
        data=GraphExtractionResponse(
            entities_created=e_count,
            relationships_created=r_count,
            entities=[
                EntityResponse(
                    id=e.id,
                    workspace_id=e.workspace_id,
                    name=e.name,
                    entity_type=e.entity_type,
                    description=e.description,
                    mention_count=e.mention_count,
                    degree=0,
                    extra_metadata=e.extra_metadata or {},
                    created_at=e.created_at,
                    updated_at=e.updated_at,
                )
                for e in entities
            ],
        ),
    )
