from __future__ import annotations

import logging
from collections import deque
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.graph import GraphEntity, GraphRelationship
from app.schemas.graph import (
    GraphPathReasoningResponse,
    GraphReasoningPath,
    InferredRelationship,
    ReasoningHop,
    RelationInferenceResponse,
)

logger = logging.getLogger("memoryverse.graph_reasoner")


class GraphReasoningEngine:
    """Multi-hop pathfinding, explanatory inference chains, and transitive hypothesis discovery across knowledge graphs."""

    TRANSITIVE_RULES: dict[tuple[str, str], str] = {
        ("DEPENDS_ON", "DEPENDS_ON"): "INDIRECTLY_DEPENDS_ON",
        ("USES", "USES"): "INDIRECTLY_USES",
        ("PART_OF", "PART_OF"): "SUBCOMPONENT_OF",
        ("USES", "PART_OF"): "COMPONENT_OF",
        ("CONTRIBUTES_TO", "PART_OF"): "ASSOCIATED_WITH",
        ("CREATES", "DEPLOYS"): "PROVISIONS",
        ("BUILT_WITH", "RUNS_ON"): "HOSTED_ON",
    }

    @classmethod
    async def resolve_entity(
        cls,
        db: AsyncSession,
        workspace_id: str,
        identifier: str,
    ) -> GraphEntity | None:
        """Resolve entity by ID or name (case-insensitive)."""
        clean_id = identifier.strip()
        # Direct ID lookup
        q_id = select(GraphEntity).where(
            GraphEntity.workspace_id == workspace_id,
            GraphEntity.id == clean_id,
        )
        entity = (await db.execute(q_id)).scalar_one_or_none()
        if entity:
            return entity

        # Case-insensitive name lookup
        q_name = select(GraphEntity).where(
            GraphEntity.workspace_id == workspace_id,
            GraphEntity.name.ilike(clean_id),
        )
        return (await db.execute(q_name)).scalars().first()

    @classmethod
    async def find_reasoning_paths(
        cls,
        db: AsyncSession,
        workspace_id: str,
        source_identifier: str,
        target_identifier: str,
        max_depth: int = 4,
    ) -> GraphPathReasoningResponse:
        """Traverse knowledge graph relationships to find explanatory multi-hop reasoning chains between two entities."""
        source = await cls.resolve_entity(db, workspace_id, source_identifier)
        target = await cls.resolve_entity(db, workspace_id, target_identifier)

        now_dt = datetime.now(UTC)

        if not source or not target:
            return GraphPathReasoningResponse(
                workspace_id=workspace_id,
                source_entity=source_identifier,
                target_entity=target_identifier,
                total_paths_found=0,
                paths=[],
                evaluated_at=now_dt,
            )

        if source.id == target.id:
            return GraphPathReasoningResponse(
                workspace_id=workspace_id,
                source_entity=source.name,
                target_entity=target.name,
                total_paths_found=1,
                paths=[
                    GraphReasoningPath(
                        path_length=0,
                        entities=[source.name],
                        relationships=[],
                        hops=[],
                        path_strength=1.0,
                        explanation=f"{source.name} is identical to {target.name}.",
                    )
                ],
                evaluated_at=now_dt,
            )

        # 1. Load entities and relationships for workspace
        ent_q = select(GraphEntity).where(GraphEntity.workspace_id == workspace_id)
        ent_rows = (await db.execute(ent_q)).scalars().all()
        id_to_name = {e.id: e.name for e in ent_rows}

        rel_q = select(GraphRelationship).where(GraphRelationship.workspace_id == workspace_id)
        rel_rows = (await db.execute(rel_q)).scalars().all()

        # Build adjacency list: node -> list of (target_node, rel_type, weight)
        adj: dict[str, list[tuple[str, str, float]]] = {}
        for r in rel_rows:
            adj.setdefault(r.source_entity_id, []).append(
                (r.target_entity_id, r.relationship_type, r.weight)
            )

        # 2. BFS Traversal for simple paths up to max_depth
        found_paths: list[GraphReasoningPath] = []
        # Queue item: (current_node, list_of_hops, visited_set)
        # hop: (source_id, rel_type, target_id, weight)
        queue: deque[tuple[str, list[tuple[str, str, str, float]], set[str]]] = deque()
        queue.append((source.id, [], {source.id}))

        while queue:
            curr_id, current_hops, visited = queue.popleft()

            if len(current_hops) >= max_depth:
                continue

            for next_id, rel_type, weight in adj.get(curr_id, []):
                if next_id in visited:
                    continue

                new_hops = current_hops + [(curr_id, rel_type, next_id, weight)]

                if next_id == target.id:
                    # Construct reasoning path
                    path_entities = [id_to_name.get(source.id, source.id)]
                    path_rels = []
                    hops_data: list[ReasoningHop] = []
                    weight_product = 1.0

                    for s_id, r_type, t_id, w in new_hops:
                        s_name = id_to_name.get(s_id, s_id)
                        t_name = id_to_name.get(t_id, t_id)
                        path_entities.append(t_name)
                        path_rels.append(r_type)
                        weight_product *= max(w, 0.1)
                        hops_data.append(
                            ReasoningHop(
                                source_name=s_name,
                                relationship=r_type,
                                target_name=t_name,
                                weight=w,
                            )
                        )

                    # Attenuate by path length
                    attenuation = 0.85 ** (len(new_hops) - 1)
                    path_strength = round(min(1.0, weight_product * attenuation), 3)

                    # Format explanation
                    explanation_parts = []
                    for h in hops_data:
                        explanation_parts.append(
                            f"{h.source_name} [{h.relationship}] -> {h.target_name}"
                        )
                    explanation = " => ".join(explanation_parts)

                    found_paths.append(
                        GraphReasoningPath(
                            path_length=len(new_hops),
                            entities=path_entities,
                            relationships=path_rels,
                            hops=hops_data,
                            path_strength=path_strength,
                            explanation=explanation,
                        )
                    )
                else:
                    new_visited = visited | {next_id}
                    queue.append((next_id, new_hops, new_visited))

        # Sort paths by path_strength descending, then path_length ascending
        found_paths.sort(key=lambda p: (-p.path_strength, p.path_length))

        return GraphPathReasoningResponse(
            workspace_id=workspace_id,
            source_entity=source.name,
            target_entity=target.name,
            total_paths_found=len(found_paths),
            paths=found_paths[:20],
            evaluated_at=now_dt,
        )

    @classmethod
    async def infer_transitive_relationships(
        cls,
        db: AsyncSession,
        workspace_id: str,
        focus_entity_id: str | None = None,
        min_confidence: float = 0.4,
        limit: int = 10,
    ) -> RelationInferenceResponse:
        """Infer implicit transitive relationships across 2-hop entity paths where no direct edge exists."""
        ent_q = select(GraphEntity).where(GraphEntity.workspace_id == workspace_id)
        ent_rows = (await db.execute(ent_q)).scalars().all()
        id_to_name = {e.id: e.name for e in ent_rows}

        rel_q = select(GraphRelationship).where(GraphRelationship.workspace_id == workspace_id)
        rel_rows = (await db.execute(rel_q)).scalars().all()

        # Existing direct edges: (source_id, target_id)
        existing_edges = {(r.source_entity_id, r.target_entity_id) for r in rel_rows}

        # Outgoing adjacency: source_id -> list of (target_id, rel_type, weight)
        out_adj: dict[str, list[tuple[str, str, float]]] = {}
        for r in rel_rows:
            out_adj.setdefault(r.source_entity_id, []).append(
                (r.target_entity_id, r.relationship_type, r.weight)
            )

        candidates: list[InferredRelationship] = []
        now_dt = datetime.now(UTC)

        nodes_to_evaluate = [focus_entity_id] if focus_entity_id else list(id_to_name.keys())

        for a_id in nodes_to_evaluate:
            if a_id not in out_adj:
                continue

            for b_id, rel_ab, w_ab in out_adj[a_id]:
                if b_id not in out_adj:
                    continue

                for c_id, rel_bc, w_bc in out_adj[b_id]:
                    # Exclude self-loops or existing direct connections
                    if a_id == c_id:
                        continue
                    if (a_id, c_id) in existing_edges:
                        continue

                    # Look up semantic rule or fall back to generic transitive connection
                    rule_key = (rel_ab.upper(), rel_bc.upper())
                    inferred_type = cls.TRANSITIVE_RULES.get(rule_key, "CONNECTED_TO")

                    # Confidence calculation
                    base_conf = (w_ab * w_bc) / (max(w_ab, 1.0) * max(w_bc, 1.0)) * 0.8
                    confidence = round(min(0.95, base_conf), 2)

                    if confidence < min_confidence:
                        continue

                    a_name = id_to_name.get(a_id, a_id)
                    b_name = id_to_name.get(b_id, b_id)
                    c_name = id_to_name.get(c_id, c_id)

                    evidence = [
                        {
                            "hop": 1,
                            "source": a_name,
                            "relationship": rel_ab,
                            "target": b_name,
                            "weight": w_ab,
                        },
                        {
                            "hop": 2,
                            "source": b_name,
                            "relationship": rel_bc,
                            "target": c_name,
                            "weight": w_bc,
                        },
                    ]

                    candidates.append(
                        InferredRelationship(
                            source_entity_id=a_id,
                            source_entity_name=a_name,
                            target_entity_id=c_id,
                            target_entity_name=c_name,
                            inferred_type=inferred_type,
                            confidence=confidence,
                            reasoning_chain=[
                                f"{a_name} [{rel_ab}] -> {b_name}",
                                f"{b_name} [{rel_bc}] -> {c_name}",
                            ],
                            evidence_hops=evidence,
                        )
                    )

        # Deduplicate candidates by (source_entity_id, target_entity_id, inferred_type)
        seen: set[tuple[str, str, str]] = set()
        deduped: list[InferredRelationship] = []
        # Sort by confidence descending
        candidates.sort(key=lambda x: x.confidence, reverse=True)

        for c in candidates:
            key = (c.source_entity_id, c.target_entity_id, c.inferred_type)
            if key not in seen:
                seen.add(key)
                deduped.append(c)
                if len(deduped) >= limit:
                    break

        return RelationInferenceResponse(
            workspace_id=workspace_id,
            total_hypotheses=len(deduped),
            inferred_relationships=deduped,
            evaluated_at=now_dt,
        )
