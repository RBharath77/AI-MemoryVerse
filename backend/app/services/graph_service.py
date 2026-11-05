import logging
from collections import Counter, defaultdict

from fastapi import HTTPException, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.graph_extractor import GraphExtractor
from app.models.graph import EntityType, GraphEntity, GraphRelationship
from app.schemas.graph import (
    EntityCreate,
    EntityUpdate,
    GraphAnalyticsResponse,
    GraphDataResponse,
    GraphEdge,
    GraphNode,
    RelationshipCreate,
)

logger = logging.getLogger(__name__)


class GraphService:
    @staticmethod
    async def create_entity(
        db: AsyncSession,
        workspace_id: str,
        data: EntityCreate,
    ) -> GraphEntity:
        clean_name = data.name.strip()

        # Check existing entity with same name and type in workspace
        query = select(GraphEntity).where(
            GraphEntity.workspace_id == workspace_id,
            GraphEntity.name.ilike(clean_name),
            GraphEntity.entity_type == data.entity_type,
        )
        res = await db.execute(query)
        existing = res.scalar_one_or_none()
        if existing:
            existing.mention_count += 1
            if data.description and not existing.description:
                existing.description = data.description
            await db.commit()
            await db.refresh(existing)
            return existing

        entity = GraphEntity(
            workspace_id=workspace_id,
            name=clean_name,
            entity_type=data.entity_type,
            description=data.description,
            extra_metadata=data.extra_metadata or {},
        )
        db.add(entity)
        await db.commit()
        await db.refresh(entity)
        return entity

    @staticmethod
    async def get_entity(
        db: AsyncSession,
        workspace_id: str,
        entity_id: str,
    ) -> tuple[GraphEntity, int]:
        query = select(GraphEntity).where(
            GraphEntity.id == entity_id,
            GraphEntity.workspace_id == workspace_id,
        )
        res = await db.execute(query)
        entity = res.scalar_one_or_none()
        if not entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Graph entity not found or unauthorized.",
            )

        degree = len(entity.outgoing_relationships) + len(entity.incoming_relationships)
        return entity, degree

    @staticmethod
    async def list_entities(
        db: AsyncSession,
        workspace_id: str,
        entity_type: EntityType | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[tuple[GraphEntity, int]], int]:
        query = select(GraphEntity).where(GraphEntity.workspace_id == workspace_id)
        if entity_type:
            query = query.where(GraphEntity.entity_type == entity_type)
        if search:
            query = query.where(
                or_(
                    GraphEntity.name.ilike(f"%{search}%"),
                    GraphEntity.description.ilike(f"%{search}%"),
                )
            )

        count_query = select(func.count(GraphEntity.id)).where(
            GraphEntity.workspace_id == workspace_id
        )
        if entity_type:
            count_query = count_query.where(GraphEntity.entity_type == entity_type)
        if search:
            count_query = count_query.where(
                or_(
                    GraphEntity.name.ilike(f"%{search}%"),
                    GraphEntity.description.ilike(f"%{search}%"),
                )
            )

        total = (await db.execute(count_query)).scalar() or 0

        query = (
            query.order_by(desc(GraphEntity.mention_count), desc(GraphEntity.created_at))
            .limit(limit)
            .offset(offset)
        )
        entities = (await db.execute(query)).scalars().all()

        results = [
            (e, len(e.outgoing_relationships) + len(e.incoming_relationships))
            for e in entities
        ]
        return results, total

    @staticmethod
    async def update_entity(
        db: AsyncSession,
        workspace_id: str,
        entity_id: str,
        data: EntityUpdate,
    ) -> GraphEntity:
        entity, _ = await GraphService.get_entity(db, workspace_id, entity_id)

        if data.name is not None and data.name.strip():
            entity.name = data.name.strip()
        if data.entity_type is not None:
            entity.entity_type = data.entity_type
        if data.description is not None:
            entity.description = data.description
        if data.extra_metadata is not None:
            entity.extra_metadata = data.extra_metadata

        await db.commit()
        await db.refresh(entity)
        return entity

    @staticmethod
    async def delete_entity(
        db: AsyncSession,
        workspace_id: str,
        entity_id: str,
    ) -> bool:
        entity, _ = await GraphService.get_entity(db, workspace_id, entity_id)
        await db.delete(entity)
        await db.commit()
        return True

    @staticmethod
    async def create_relationship(
        db: AsyncSession,
        workspace_id: str,
        data: RelationshipCreate,
    ) -> GraphRelationship:
        # Tenancy validation on both source and target entities
        src, _ = await GraphService.get_entity(db, workspace_id, data.source_entity_id)
        tgt, _ = await GraphService.get_entity(db, workspace_id, data.target_entity_id)

        if src.id == tgt.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Source and target entities cannot be the same.",
            )

        # Check existing edge
        rel_type = data.relationship_type.strip().lower().replace(" ", "_")
        q = select(GraphRelationship).where(
            GraphRelationship.workspace_id == workspace_id,
            GraphRelationship.source_entity_id == src.id,
            GraphRelationship.target_entity_id == tgt.id,
            GraphRelationship.relationship_type == rel_type,
        )
        existing = (await db.execute(q)).scalar_one_or_none()
        if existing:
            existing.weight += data.weight
            await db.commit()
            rel_q = (
                select(GraphRelationship)
                .options(
                    selectinload(GraphRelationship.source_entity),
                    selectinload(GraphRelationship.target_entity),
                )
                .where(GraphRelationship.id == existing.id)
            )
            return (await db.execute(rel_q)).scalar_one()

        rel = GraphRelationship(
            workspace_id=workspace_id,
            source_entity_id=src.id,
            target_entity_id=tgt.id,
            relationship_type=rel_type,
            weight=data.weight,
            source_memory_id=data.source_memory_id,
            source_document_id=data.source_document_id,
            extra_metadata=data.extra_metadata or {},
        )
        db.add(rel)
        await db.commit()
        rel_q = (
            select(GraphRelationship)
            .options(
                selectinload(GraphRelationship.source_entity),
                selectinload(GraphRelationship.target_entity),
            )
            .where(GraphRelationship.id == rel.id)
        )
        return (await db.execute(rel_q)).scalar_one()

    @staticmethod
    async def delete_relationship(
        db: AsyncSession,
        workspace_id: str,
        relationship_id: str,
    ) -> bool:
        q = select(GraphRelationship).where(
            GraphRelationship.id == relationship_id,
            GraphRelationship.workspace_id == workspace_id,
        )
        rel = (await db.execute(q)).scalar_one_or_none()
        if not rel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Graph relationship not found or unauthorized.",
            )
        await db.delete(rel)
        await db.commit()
        return True

    @staticmethod
    async def get_workspace_graph(
        db: AsyncSession,
        workspace_id: str,
        limit_nodes: int = 250,
    ) -> GraphDataResponse:
        e_query = (
            select(GraphEntity)
            .where(GraphEntity.workspace_id == workspace_id)
            .order_by(desc(GraphEntity.mention_count))
            .limit(limit_nodes)
        )
        entities = list((await db.execute(e_query)).scalars().all())
        entity_ids = {e.id for e in entities}

        if not entity_ids:
            return GraphDataResponse(nodes=[], edges=[], total_nodes=0, total_edges=0)

        r_query = select(GraphRelationship).where(
            GraphRelationship.workspace_id == workspace_id,
            GraphRelationship.source_entity_id.in_(entity_ids),
            GraphRelationship.target_entity_id.in_(entity_ids),
        )
        relationships = list((await db.execute(r_query)).scalars().all())

        # Compute degrees
        degrees: dict[str, int] = defaultdict(int)
        for r in relationships:
            degrees[r.source_entity_id] += 1
            degrees[r.target_entity_id] += 1

        nodes = [
            GraphNode(
                id=e.id,
                name=e.name,
                entity_type=e.entity_type.value,
                mention_count=e.mention_count,
                degree=degrees[e.id],
            )
            for e in entities
        ]

        edges = [
            GraphEdge(
                id=r.id,
                source=r.source_entity_id,
                target=r.target_entity_id,
                relationship_type=r.relationship_type,
                weight=r.weight,
            )
            for r in relationships
        ]

        return GraphDataResponse(
            nodes=nodes,
            edges=edges,
            total_nodes=len(nodes),
            total_edges=len(edges),
        )

    @staticmethod
    async def get_neighborhood(
        db: AsyncSession,
        workspace_id: str,
        entity_id: str,
    ) -> GraphDataResponse:
        center_entity, _ = await GraphService.get_entity(db, workspace_id, entity_id)

        # Direct edges
        r_query = select(GraphRelationship).where(
            GraphRelationship.workspace_id == workspace_id,
            or_(
                GraphRelationship.source_entity_id == entity_id,
                GraphRelationship.target_entity_id == entity_id,
            ),
        )
        direct_edges = list((await db.execute(r_query)).scalars().all())

        neighbor_ids = {entity_id}
        for edge in direct_edges:
            neighbor_ids.add(edge.source_entity_id)
            neighbor_ids.add(edge.target_entity_id)

        e_query = select(GraphEntity).where(
            GraphEntity.workspace_id == workspace_id,
            GraphEntity.id.in_(neighbor_ids),
        )
        neighbor_entities = list((await db.execute(e_query)).scalars().all())

        degrees: dict[str, int] = defaultdict(int)
        for r in direct_edges:
            degrees[r.source_entity_id] += 1
            degrees[r.target_entity_id] += 1

        nodes = [
            GraphNode(
                id=e.id,
                name=e.name,
                entity_type=e.entity_type.value,
                mention_count=e.mention_count,
                degree=degrees[e.id],
            )
            for e in neighbor_entities
        ]
        edges = [
            GraphEdge(
                id=r.id,
                source=r.source_entity_id,
                target=r.target_entity_id,
                relationship_type=r.relationship_type,
                weight=r.weight,
            )
            for r in direct_edges
        ]

        return GraphDataResponse(
            nodes=nodes,
            edges=edges,
            total_nodes=len(nodes),
            total_edges=len(edges),
        )

    @staticmethod
    async def extract_and_ingest(
        db: AsyncSession,
        workspace_id: str,
        text: str,
        source_memory_id: str | None = None,
        source_document_id: str | None = None,
    ) -> tuple[int, int, list[GraphEntity]]:
        extracted = await GraphExtractor.extract(text)

        created_entities: list[GraphEntity] = []
        name_to_entity: dict[str, GraphEntity] = {}

        for ent_data in extracted.entities:
            entity = await GraphService.create_entity(
                db=db,
                workspace_id=workspace_id,
                data=EntityCreate(
                    name=ent_data.name,
                    entity_type=ent_data.entity_type,
                    description=ent_data.description,
                ),
            )
            created_entities.append(entity)
            name_to_entity[entity.name.lower()] = entity

        rel_count = 0
        for rel_data in extracted.relationships:
            src_ent = name_to_entity.get(rel_data.source_name.lower())
            tgt_ent = name_to_entity.get(rel_data.target_name.lower())

            if src_ent and tgt_ent and src_ent.id != tgt_ent.id:
                try:
                    await GraphService.create_relationship(
                        db=db,
                        workspace_id=workspace_id,
                        data=RelationshipCreate(
                            source_entity_id=src_ent.id,
                            target_entity_id=tgt_ent.id,
                            relationship_type=rel_data.relationship_type,
                            source_memory_id=source_memory_id,
                            source_document_id=source_document_id,
                        ),
                    )
                    rel_count += 1
                except Exception as e:
                    logger.warning(f"Skipped relationship creation: {e}")

        return len(created_entities), rel_count, created_entities

    @staticmethod
    async def get_analytics(
        db: AsyncSession,
        workspace_id: str,
    ) -> GraphAnalyticsResponse:
        entities = list(
            (
                await db.execute(
                    select(GraphEntity).where(GraphEntity.workspace_id == workspace_id)
                )
            ).scalars().all()
        )
        relationships = list(
            (
                await db.execute(
                    select(GraphRelationship).where(GraphRelationship.workspace_id == workspace_id)
                )
            ).scalars().all()
        )

        total_entities = len(entities)
        total_relationships = len(relationships)

        type_counts = Counter(e.entity_type.value for e in entities)

        degrees: dict[str, int] = defaultdict(int)
        for r in relationships:
            degrees[r.source_entity_id] += 1
            degrees[r.target_entity_id] += 1

        top_central = sorted(
            [
                {
                    "id": e.id,
                    "name": e.name,
                    "entity_type": e.entity_type.value,
                    "degree": degrees[e.id],
                    "mention_count": e.mention_count,
                }
                for e in entities
            ],
            key=lambda x: x["degree"],
            reverse=True,
        )[:10]

        avg_degree = (2.0 * total_relationships / total_entities) if total_entities > 0 else 0.0

        return GraphAnalyticsResponse(
            total_entities=total_entities,
            total_relationships=total_relationships,
            entity_type_breakdown=dict(type_counts),
            top_central_entities=top_central,
            average_degree=round(avg_degree, 2),
        )
