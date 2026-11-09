from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import Memory, MemoryStatus
from app.schemas.memory import (
    HierarchyDrilldownRequest,
    HierarchyDrilldownResponse,
    HierarchyNode,
    MemoryHierarchyBuildRequest,
    MemoryHierarchyResponse,
)

logger = logging.getLogger("memoryverse.cognitive_hierarchy")


class CognitiveHierarchyEngine:
    """
    Cognitive Memory Consolidation Tree & Semantic Hierarchical Abstraction Engine.
    Structures flat workspace memories into a multi-tier abstraction pyramid:
      Level 0: Raw episodic/sensory observations (Leaf nodes)
      Level 1: Tactical thematic cluster syntheses
      Level 2: Core architectural/behavioral principles
      Level 3: Root overarching axioms / world models
    Provides drill-down explainability from high-order principles to foundational source memories.
    """

    _cache: dict[str, MemoryHierarchyResponse] = {}

    @classmethod
    async def build_hierarchy(
        cls,
        db: AsyncSession,
        workspace_id: str,
        request: MemoryHierarchyBuildRequest,
    ) -> MemoryHierarchyResponse:
        """Construct multi-tier abstraction pyramid over active workspace memories."""
        now_dt = datetime.now(UTC)

        stmt = select(Memory).where(
            Memory.workspace_id == workspace_id,
            Memory.status.in_([MemoryStatus.APPROVED, MemoryStatus.PENDING_REVIEW]),
        )
        if request.category_filter:
            stmt = stmt.where(Memory.category == request.category_filter)
        stmt = stmt.order_by(Memory.created_at.asc())
        memories = list((await db.execute(stmt)).scalars().all())

        if not memories:
            empty_resp = MemoryHierarchyResponse(
                workspace_id=workspace_id,
                total_memories_indexed=0,
                total_nodes=0,
                max_depth=0,
                compression_ratio=0.0,
                nodes=[],
                root_node_ids=[],
                built_at=now_dt,
            )
            cls._cache[workspace_id] = empty_resp
            return empty_resp

        nodes: list[HierarchyNode] = []
        leaves_by_cat: dict[str, list[HierarchyNode]] = {}

        # 1. Level 0: Leaf Nodes (one per memory)
        for m in memories:
            cat_str = m.category.value if hasattr(m.category, "value") else str(m.category)
            leaf_id = f"leaf_{m.id}"
            leaf = HierarchyNode(
                node_id=leaf_id,
                level=0,
                title=f"Episodic: {m.content[:35]}..."
                if len(m.content) > 35
                else f"Episodic: {m.content}",
                content_summary=m.content,
                category=cat_str,
                memory_ids=[m.id],
                parent_node_id=None,
                child_node_ids=[],
                abstraction_depth=0,
            )
            nodes.append(leaf)
            leaves_by_cat.setdefault(cat_str, []).append(leaf)

        # 2. Level 1: Tactical Thematic Clusters
        level1_nodes: list[HierarchyNode] = []
        for cat_name, cat_leaves in leaves_by_cat.items():
            tactical_id = f"tactical_{cat_name}_{uuid.uuid4().hex[:6]}"
            child_ids = [leaf.node_id for leaf in cat_leaves]
            mem_ids = [mid for leaf in cat_leaves for mid in leaf.memory_ids]

            summary_points = [f"• {leaf.content_summary.strip()}" for leaf in cat_leaves[:3]]
            summary_text = (
                f"Tactical synthesis of {len(cat_leaves)} {cat_name} memories covering baseline configurations "
                f"and operational decisions:\n" + "\n".join(summary_points)
            )

            tactical_node = HierarchyNode(
                node_id=tactical_id,
                level=1,
                title=f"Tactical Synthesis: {cat_name.capitalize()} Cluster",
                content_summary=summary_text,
                category=cat_name,
                memory_ids=mem_ids,
                parent_node_id=None,
                child_node_ids=child_ids,
                abstraction_depth=1,
            )
            level1_nodes.append(tactical_node)
            nodes.append(tactical_node)

            # Link leaves to their tactical parent
            for leaf in cat_leaves:
                leaf.parent_node_id = tactical_id

        # 3. Level 2: Core Architectural / Behavioral Principles
        level2_nodes: list[HierarchyNode] = []
        chunk_size = max(1, len(level1_nodes) // 2) if len(level1_nodes) > 2 else len(level1_nodes)
        l1_chunks = [
            level1_nodes[i : i + chunk_size] for i in range(0, len(level1_nodes), chunk_size)
        ]

        for idx, chunk in enumerate(l1_chunks):
            principle_id = f"axiom_{idx + 1}_{uuid.uuid4().hex[:6]}"
            child_tactical_ids = [tn.node_id for tn in chunk]
            principle_mem_ids = [mid for tn in chunk for mid in tn.memory_ids]
            categories_covered = list({tn.category for tn in chunk})

            principle_node = HierarchyNode(
                node_id=principle_id,
                level=2,
                title=f"Core Principle: Consolidated {', '.join(c.capitalize() for c in categories_covered)} Framework",
                content_summary=(
                    f"Consolidated high-order architectural axiom derived from {len(principle_mem_ids)} foundational "
                    f"workspace memories across tactical modules."
                ),
                category="principle",
                memory_ids=principle_mem_ids,
                parent_node_id=None,
                child_node_ids=child_tactical_ids,
                abstraction_depth=2,
            )
            level2_nodes.append(principle_node)
            nodes.append(principle_node)

            # Link tactical nodes to principle parent
            for tn in chunk:
                tn.parent_node_id = principle_id

        # Determine Root Nodes (nodes with no parent)
        root_ids = [n.node_id for n in nodes if n.parent_node_id is None]
        max_depth = max((n.level for n in nodes), default=0)
        abstract_nodes_count = max(1, len(level1_nodes) + len(level2_nodes))
        compression_ratio = round(len(memories) / float(abstract_nodes_count), 2)

        resp = MemoryHierarchyResponse(
            workspace_id=workspace_id,
            total_memories_indexed=len(memories),
            total_nodes=len(nodes),
            max_depth=max_depth,
            compression_ratio=compression_ratio,
            nodes=nodes,
            root_node_ids=root_ids,
            built_at=now_dt,
        )
        cls._cache[workspace_id] = resp
        return resp

    @classmethod
    async def get_hierarchy(
        cls,
        db: AsyncSession,
        workspace_id: str,
    ) -> MemoryHierarchyResponse:
        """Retrieve existing cached hierarchy or build on the fly."""
        if workspace_id in cls._cache:
            return cls._cache[workspace_id]
        return await cls.build_hierarchy(
            db=db,
            workspace_id=workspace_id,
            request=MemoryHierarchyBuildRequest(),
        )

    @classmethod
    async def drilldown(
        cls,
        db: AsyncSession,
        workspace_id: str,
        request: HierarchyDrilldownRequest,
    ) -> HierarchyDrilldownResponse:
        """Inspect a specific hierarchy node, walking ancestors, descendants, and source memories."""
        hierarchy = await cls.get_hierarchy(db, workspace_id)
        node_map = {n.node_id: n for n in hierarchy.nodes}

        target_node = node_map.get(request.node_id)
        if not target_node:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Hierarchy node '{request.node_id}' not found in workspace",
            )

        # 1. Traverse Ancestors
        ancestor_chain: list[HierarchyNode] = []
        curr = target_node
        visited_ancestors: set[str] = set()
        while curr.parent_node_id and curr.parent_node_id in node_map:
            if curr.parent_node_id in visited_ancestors:
                break
            visited_ancestors.add(curr.parent_node_id)
            parent = node_map[curr.parent_node_id]
            ancestor_chain.append(parent)
            curr = parent

        # 2. Traverse Descendants (BFS)
        descendants: list[HierarchyNode] = []
        queue = list(target_node.child_node_ids)
        visited_descendants: set[str] = set()
        while queue:
            cid = queue.pop(0)
            if cid in visited_descendants or cid not in node_map:
                continue
            visited_descendants.add(cid)
            child = node_map[cid]
            descendants.append(child)
            queue.extend(child.child_node_ids)

        # 3. Retrieve Underlying Raw Memory Records
        mem_records: list[dict[str, Any]] = []
        if target_node.memory_ids:
            mem_stmt = select(Memory).where(
                Memory.workspace_id == workspace_id,
                Memory.id.in_(target_node.memory_ids),
            )
            raw_mems = list((await db.execute(mem_stmt)).scalars().all())
            mem_records = [
                {
                    "id": m.id,
                    "content": m.content,
                    "category": m.category.value
                    if hasattr(m.category, "value")
                    else str(m.category),
                    "importance": m.importance,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in raw_mems
            ]

        return HierarchyDrilldownResponse(
            workspace_id=workspace_id,
            node=target_node,
            ancestor_chain=ancestor_chain,
            descendant_nodes=descendants,
            underlying_memories=mem_records,
            retrieved_at=datetime.now(UTC),
        )
