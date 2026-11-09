from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.retrieval import cosine_similarity
from app.models.graph import GraphEntity, GraphRelationship
from app.models.memory import Memory, MemoryLink, MemoryStatus

logger = logging.getLogger("memoryverse.associative_memory")


@dataclass
class ActivatedNodeData:
    node_id: str
    node_type: str
    content: str
    activation_energy: float
    hop_distance: int
    relationship_path: list[str] = field(default_factory=list)


class AssociativeMemoryExplorer:
    """Spreading activation graph explorer modeling human cognitive memory association across multi-hop edges."""

    @classmethod
    async def explore_associations(
        cls,
        db: AsyncSession,
        workspace_id: str,
        seed_memory_id: str,
        max_hops: int = 2,
        decay_factor: float = 0.65,
        min_activation: float = 0.15,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Traverse memory links, semantic similarity neighbors, and graph entities using spreading activation."""
        now_dt = datetime.now(UTC)

        # 1. Fetch seed memory
        seed_mem = await db.get(Memory, seed_memory_id)
        if not seed_mem or seed_mem.workspace_id != workspace_id:
            return {
                "seed_memory_id": seed_memory_id,
                "seed_content": "",
                "total_activated_nodes": 0,
                "associations": [],
                "max_activation": 0.0,
                "explored_at": now_dt,
            }

        activated: dict[str, ActivatedNodeData] = {}

        # 2. Hop 1: Explicit MemoryLink records
        links_q = select(MemoryLink).where(
            MemoryLink.workspace_id == workspace_id,
            or_(
                MemoryLink.source_memory_id == seed_memory_id,
                MemoryLink.target_memory_id == seed_memory_id,
            ),
        )
        links = list((await db.execute(links_q)).scalars().all())

        hop1_mem_ids: set[str] = set()
        for link in links:
            neighbor_id = (
                link.target_memory_id
                if link.source_memory_id == seed_memory_id
                else link.source_memory_id
            )
            if neighbor_id == seed_memory_id:
                continue

            target_mem = await db.get(Memory, neighbor_id)
            if target_mem and target_mem.status == MemoryStatus.APPROVED:
                energy = round(1.0 * (link.confidence or 1.0) * decay_factor, 3)
                if energy >= min_activation:
                    rel_name = link.relationship_type or "LINKED"
                    activated[neighbor_id] = ActivatedNodeData(
                        node_id=neighbor_id,
                        node_type="memory",
                        content=target_mem.content,
                        activation_energy=energy,
                        hop_distance=1,
                        relationship_path=[f"MemoryLink:{rel_name}"],
                    )
                    hop1_mem_ids.add(neighbor_id)

        # 3. Hop 1: Vector/Cosine Semantic Similarity Neighbors
        if seed_mem.embedding is not None:
            cand_q = (
                select(Memory)
                .where(
                    Memory.workspace_id == workspace_id,
                    Memory.status == MemoryStatus.APPROVED,
                    Memory.id != seed_memory_id,
                )
                .limit(50)
            )
            cand_mems = list((await db.execute(cand_q)).scalars().all())

            for cand in cand_mems:
                if cand.id in activated:
                    continue
                if cand.embedding is not None:
                    sim = cosine_similarity(seed_mem.embedding, cand.embedding)
                    if sim >= 0.55:
                        energy = round(1.0 * sim * decay_factor, 3)
                        if energy >= min_activation:
                            activated[cand.id] = ActivatedNodeData(
                                node_id=cand.id,
                                node_type="memory",
                                content=cand.content,
                                activation_energy=energy,
                                hop_distance=1,
                                relationship_path=[f"SemanticSimilarity:{sim:.2f}"],
                            )
                            hop1_mem_ids.add(cand.id)

        # 4. Hop 1: Knowledge Graph Entity & Relationship Co-Occurrence
        rel_q = (
            select(GraphRelationship)
            .where(
                GraphRelationship.workspace_id == workspace_id,
                GraphRelationship.source_memory_id == seed_memory_id,
            )
            .limit(10)
        )
        rels = list((await db.execute(rel_q)).scalars().all())

        for rel in rels:
            for ent_id in (rel.source_entity_id, rel.target_entity_id):
                ent = await db.get(GraphEntity, ent_id)
                if ent and ent.id not in activated:
                    ent_energy = round(1.0 * (rel.weight or 0.85) * decay_factor, 3)
                    if ent_energy >= min_activation:
                        activated[ent.id] = ActivatedNodeData(
                            node_id=ent.id,
                            node_type="entity",
                            content=f"Entity [{ent.entity_type}]: {ent.name}",
                            activation_energy=ent_energy,
                            hop_distance=1,
                            relationship_path=[f"GraphRel:{rel.relationship_type}"],
                        )

        # Also search entities matching tags or extra_metadata
        if seed_mem.tags:
            for tag in seed_mem.tags:
                if isinstance(tag, str) and len(tag) > 2:
                    ent_tag_q = (
                        select(GraphEntity)
                        .where(
                            GraphEntity.workspace_id == workspace_id,
                            GraphEntity.name.ilike(f"%{tag}%"),
                        )
                        .limit(5)
                    )
                    tag_ents = list((await db.execute(ent_tag_q)).scalars().all())
                    for te in tag_ents:
                        if te.id not in activated:
                            t_energy = round(1.0 * 0.75 * decay_factor, 3)
                            if t_energy >= min_activation:
                                activated[te.id] = ActivatedNodeData(
                                    node_id=te.id,
                                    node_type="entity",
                                    content=f"Entity [{te.entity_type}]: {te.name}",
                                    activation_energy=t_energy,
                                    hop_distance=1,
                                    relationship_path=[f"TagEntityMatch:{tag}"],
                                )

        # 5. Hop 2: Propagate activation from Hop 1 memories
        if max_hops >= 2 and hop1_mem_ids:
            for h1_id in list(hop1_mem_ids)[:5]:
                h1_data = activated.get(h1_id)
                if not h1_data:
                    continue

                h2_links_q = (
                    select(MemoryLink)
                    .where(
                        MemoryLink.workspace_id == workspace_id,
                        or_(
                            MemoryLink.source_memory_id == h1_id,
                            MemoryLink.target_memory_id == h1_id,
                        ),
                    )
                    .limit(5)
                )
                h2_links = list((await db.execute(h2_links_q)).scalars().all())

                for l2 in h2_links:
                    h2_id = (
                        l2.target_memory_id if l2.source_memory_id == h1_id else l2.source_memory_id
                    )
                    if h2_id == seed_memory_id or h2_id in activated:
                        continue

                    h2_mem = await db.get(Memory, h2_id)
                    if h2_mem and h2_mem.status == MemoryStatus.APPROVED:
                        h2_energy = round(
                            h1_data.activation_energy * (l2.confidence or 1.0) * decay_factor, 3
                        )
                        if h2_energy >= min_activation:
                            activated[h2_id] = ActivatedNodeData(
                                node_id=h2_id,
                                node_type="memory",
                                content=h2_mem.content,
                                activation_energy=h2_energy,
                                hop_distance=2,
                                relationship_path=h1_data.relationship_path
                                + [f"MemoryLink:{l2.relationship_type}"],
                            )

        # Sort activated nodes by activation energy descending
        sorted_nodes = sorted(
            activated.values(),
            key=lambda x: x.activation_energy,
            reverse=True,
        )[:limit]

        max_act = sorted_nodes[0].activation_energy if sorted_nodes else 0.0

        return {
            "seed_memory_id": seed_memory_id,
            "seed_content": seed_mem.content,
            "total_activated_nodes": len(sorted_nodes),
            "associations": [
                {
                    "node_id": n.node_id,
                    "node_type": n.node_type,
                    "content": n.content,
                    "activation_energy": n.activation_energy,
                    "hop_distance": n.hop_distance,
                    "relationship_path": n.relationship_path,
                }
                for n in sorted_nodes
            ],
            "max_activation": max_act,
            "explored_at": now_dt,
        }
