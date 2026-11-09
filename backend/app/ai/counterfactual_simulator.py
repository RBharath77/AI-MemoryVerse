from __future__ import annotations

import logging
from collections import deque
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.graph import GraphEntity, GraphRelationship
from app.schemas.graph import (
    CounterfactualSimulationRequest,
    CounterfactualSimulationResponse,
    ImpactedNode,
    RiskTradeOffItem,
)

logger = logging.getLogger("memoryverse.counterfactual_simulator")


class CounterfactualSimulator:
    """
    Semantic Knowledge Graph Counterfactual & "What-If" Simulation Engine.
    Simulates hypothetical architectural changes, service migrations, or component deprecations,
    traversing multi-hop dependency graphs to compute downstream ripple effects,
    architectural trade-offs, and blast radius scores.
    """

    # Domain risk rule heuristics
    COMPONENT_RISK_RULES = {
        "database": {
            "keywords": [
                "database",
                "postgres",
                "sql",
                "clickhouse",
                "sqlite",
                "vector",
                "pgvector",
                "storage",
            ],
            "risks": [
                RiskTradeOffItem(
                    category="data_loss",
                    severity="HIGH",
                    description="Storage/database substitution requires schema translation, dual-write synchronization, and data migration.",
                    mitigation_strategy="Execute zero-downtime shadow dual-writing and verify cryptographic hash chain parity before cutover.",
                ),
                RiskTradeOffItem(
                    category="performance",
                    severity="MEDIUM",
                    description="Query execution plans and vector indexing throughput may degrade under different connection pooling models.",
                    mitigation_strategy="Benchmark query latencies under 20-thread concurrency using automated load fixtures.",
                ),
            ],
            "preconditions": [
                "Generate automated full PostgreSQL database snapshot and verify restore.",
                "Ensure zero uncommitted async sessions before triggering schema mutations.",
            ],
        },
        "worker": {
            "keywords": [
                "celery",
                "temporal",
                "worker",
                "queue",
                "redis",
                "async",
                "task",
                "job",
                "background",
            ],
            "risks": [
                RiskTradeOffItem(
                    category="operational",
                    severity="HIGH",
                    description="Switching queue broker or workflow orchestrator risks dropping in-flight tasks and breaking task idempotency.",
                    mitigation_strategy="Drain active task queues to zero before cutover and verify Idempotency-Key persistence.",
                ),
                RiskTradeOffItem(
                    category="architecture",
                    severity="MEDIUM",
                    description="Orchestrator APIs differ in retry backoff, deterministic replay constraints, and event broadcasting.",
                    mitigation_strategy="Implement pluggable TaskOrchestrator adapter conforming to BaseWorkerProvider interface.",
                ),
            ],
            "preconditions": [
                "Drain all active and scheduled background tasks.",
                "Verify task failure recovery and dead-letter queue (DLQ) redrive protocols.",
            ],
        },
        "security": {
            "keywords": [
                "auth",
                "jwt",
                "hmac",
                "cmek",
                "token",
                "encryption",
                "mfa",
                "rbac",
                "secret",
            ],
            "risks": [
                RiskTradeOffItem(
                    category="security",
                    severity="CRITICAL",
                    description="Altering cryptographic algorithms or authentication primitives risks mass session invalidation or bypass.",
                    mitigation_strategy="Deploy dual-key verification window with phased token versioning (`token_version`).",
                )
            ],
            "preconditions": [
                "Ensure active cryptographic key rotation is complete.",
                "Enforce multi-tenant cryptographic isolation regression tests.",
            ],
        },
        "frontend": {
            "keywords": ["react", "next.js", "vue", "tailwind", "ui", "frontend", "component"],
            "risks": [
                RiskTradeOffItem(
                    category="operational",
                    severity="MEDIUM",
                    description="Component framework transition introduces client-side hydration mismatches and theme contrast variations.",
                    mitigation_strategy="Run automated Next.js static build checks and verify WCAG 2.1 AA accessibility contrast.",
                )
            ],
            "preconditions": [
                "Verify static compilation across all App Router routes.",
                "Execute lighthouse accessibility and Core Web Vitals audit.",
            ],
        },
    }

    @classmethod
    async def simulate(
        cls,
        db: AsyncSession,
        workspace_id: str,
        request: CounterfactualSimulationRequest,
    ) -> CounterfactualSimulationResponse:
        """
        Execute counterfactual simulation over workspace knowledge graph and dependencies.
        """
        now_dt = datetime.now(UTC)

        # 1. Fetch all workspace graph entities and relationships
        ent_stmt = select(GraphEntity).where(GraphEntity.workspace_id == workspace_id)
        entities = list((await db.execute(ent_stmt)).scalars().all())

        rel_stmt = select(GraphRelationship).where(GraphRelationship.workspace_id == workspace_id)
        relationships = list((await db.execute(rel_stmt)).scalars().all())

        # Map entities by ID and name (lowercased)
        id_to_ent: dict[str, GraphEntity] = {e.id: e for e in entities}
        name_to_id: dict[str, str] = {e.name.lower(): e.id for e in entities}

        # Build bidirectional adjacency list for ripple traversal
        # adj[source_id] -> list of (target_id, relationship_type)
        adj: dict[str, list[tuple[str, str]]] = {e.id: [] for e in entities}
        for r in relationships:
            if r.source_entity_id in adj and r.target_entity_id in adj:
                adj[r.source_entity_id].append((r.target_entity_id, r.relationship_type))
                adj[r.target_entity_id].append(
                    (r.source_entity_id, f"REVERSE_{r.relationship_type}")
                )

        # 2. Identify Direct Focal Targets
        direct_ids: set[str] = set()
        for target_str in request.target_entities:
            t_lower = target_str.strip().lower()
            if t_lower in name_to_id:
                direct_ids.add(name_to_id[t_lower])
            elif target_str in id_to_ent:
                direct_ids.add(target_str)
            else:
                # Substring match
                for name, e_id in name_to_id.items():
                    if t_lower in name or name in t_lower:
                        direct_ids.add(e_id)

        # Fallback if no matching graph node exists yet
        if not direct_ids and entities:
            # Pick first available or match against scenario text
            for name, e_id in name_to_id.items():
                if name in request.scenario_text.lower():
                    direct_ids.add(e_id)
            if not direct_ids:
                direct_ids.add(entities[0].id)

        # 3. Multi-Hop Ripple Traversal (BFS)
        visited_nodes: dict[str, int] = {}  # node_id -> hop_distance
        node_rel_paths: dict[str, list[str]] = {node_id: [] for node_id in direct_ids}

        queue: deque[tuple[str, int, list[str]]] = deque()
        for d_id in direct_ids:
            visited_nodes[d_id] = 0
            queue.append((d_id, 0, []))

        while queue:
            curr_id, curr_hop, path_rels = queue.popleft()
            if curr_hop >= request.max_ripple_depth:
                continue

            for neighbor_id, rel_type in adj.get(curr_id, []):
                if neighbor_id not in visited_nodes:
                    visited_nodes[neighbor_id] = curr_hop + 1
                    node_rel_paths[neighbor_id] = path_rels + [rel_type]
                    queue.append((neighbor_id, curr_hop + 1, path_rels + [rel_type]))

        # 4. Construct ImpactedNode Records
        impacted_nodes: list[ImpactedNode] = []
        direct_count = 0
        cascading_count = 0

        for node_id, hop_dist in visited_nodes.items():
            ent = id_to_ent.get(node_id)
            if not ent:
                continue

            is_direct = hop_dist == 0
            if is_direct:
                direct_count += 1
            else:
                cascading_count += 1

            impacted_nodes.append(
                ImpactedNode(
                    entity_id=ent.id,
                    entity_name=ent.name,
                    entity_type=(
                        ent.entity_type.value
                        if hasattr(ent.entity_type, "value")
                        else str(ent.entity_type)
                    ),
                    impact_type="DIRECT" if is_direct else "TRANSITIVE",
                    hop_distance=hop_dist,
                    connected_relationships=node_rel_paths.get(node_id, []),
                )
            )

        # Sort: Direct nodes first, then by hop distance
        impacted_nodes.sort(
            key=lambda x: (0 if x.impact_type == "DIRECT" else 1, x.hop_distance, x.entity_name)
        )

        # 5. Risk Assessment & Trade-off Identification
        risks: list[RiskTradeOffItem] = []
        preconditions: set[str] = {
            "Create database backup snapshot and export compliance audit state.",
            "Run full automated unit and regression test suites before staging cutover.",
        }

        scenario_corpus = f"{request.scenario_text} {' '.join(request.target_entities)} {request.replacement_target or ''}".lower()

        matched_rule = False
        for rule_key, rule_data in cls.COMPONENT_RISK_RULES.items():
            if any(kw in scenario_corpus for kw in rule_data["keywords"]):
                matched_rule = True
                risks.extend(rule_data["risks"])
                preconditions.update(rule_data["preconditions"])

        if not matched_rule:
            risks.append(
                RiskTradeOffItem(
                    category="architecture",
                    severity="MEDIUM",
                    description=f"Action '{request.proposed_action}' modifies component contracts without standardized automated adapter.",
                    mitigation_strategy="Define explicit interface boundary and regression test suites for all affected dependents.",
                )
            )

        # 6. Blast Radius Score Calculation
        total_graph_size = max(len(entities), 5)
        raw_blast = (direct_count * 2.0 + cascading_count * 1.0) / total_graph_size
        blast_radius = min(1.0, round(raw_blast, 3))

        return CounterfactualSimulationResponse(
            workspace_id=workspace_id,
            scenario=request.scenario_text,
            proposed_action=request.proposed_action,
            target_entities=request.target_entities,
            replacement_target=request.replacement_target,
            direct_impact_count=direct_count,
            cascading_impact_count=cascading_count,
            blast_radius_score=blast_radius,
            impacted_entities=impacted_nodes,
            risks_and_tradeoffs=risks,
            recommended_preconditions=sorted(list(preconditions)),
            simulated_at=now_dt,
        )
