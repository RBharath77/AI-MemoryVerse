from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import AuditEvent
from app.schemas.billing import (
    MerkleAuditRootResponse,
    MerkleProofResponse,
    MerkleProofVerificationResponse,
)

logger = logging.getLogger("memoryverse.merkle")


class MerkleAuditEngine:
    """Cryptographic Merkle Tree Engine for high-assurance audit log inclusion proofs and tamper attestation."""

    @staticmethod
    def hash_leaf(event: AuditEvent | dict[str, Any]) -> str:
        """Compute the leaf hash using RFC 6962 domain separation (leaf: prefix)."""
        if isinstance(event, AuditEvent):
            details_copy = dict(event.details or {})
            details_copy.pop("_chain", None)
            created_str = event.created_at.isoformat() if event.created_at else ""
            canonical_payload = {
                "id": str(event.id),
                "action": str(event.action),
                "user_id": str(event.user_id or ""),
                "workspace_id": str(event.workspace_id or ""),
                "created_at": created_str,
                "details": details_copy,
            }
        else:
            details_copy = dict(event.get("details") or {})
            details_copy.pop("_chain", None)
            created_val = event.get("created_at")
            if isinstance(created_val, datetime):
                created_str = created_val.isoformat()
            else:
                created_str = str(created_val or "")
            canonical_payload = {
                "id": str(event.get("id", "")),
                "action": str(event.get("action", "")),
                "user_id": str(event.get("user_id") or ""),
                "workspace_id": str(event.get("workspace_id") or ""),
                "created_at": created_str,
                "details": details_copy,
            }

        canonical_json = json.dumps(canonical_payload, sort_keys=True, default=str)
        raw_leaf = f"leaf:{canonical_json}"
        return hashlib.sha256(raw_leaf.encode("utf-8")).hexdigest()

    @staticmethod
    def hash_nodes(left: str, right: str) -> str:
        """Compute interior node hash using RFC 6962 domain separation (node: prefix)."""
        raw_node = f"node:{left}:{right}"
        return hashlib.sha256(raw_node.encode("utf-8")).hexdigest()

    @classmethod
    def build_tree(cls, leaf_hashes: list[str]) -> list[list[str]]:
        """
        Build full binary Merkle tree levels from bottom (leaves) to top (root).
        Pads odd leaf counts at each level by duplicating the terminal node.
        """
        if not leaf_hashes:
            empty_root = hashlib.sha256(b"empty_root").hexdigest()
            return [[empty_root]]

        levels: list[list[str]] = [list(leaf_hashes)]
        current_level = list(leaf_hashes)

        while len(current_level) > 1:
            next_level: list[str] = []
            if len(current_level) % 2 != 0:
                current_level.append(current_level[-1])

            for i in range(0, len(current_level), 2):
                parent_hash = cls.hash_nodes(current_level[i], current_level[i + 1])
                next_level.append(parent_hash)

            levels.append(next_level)
            current_level = next_level

        return levels

    @classmethod
    def get_merkle_root(cls, leaf_hashes: list[str]) -> str:
        """Calculate the Merkle root hash for a collection of leaf hashes."""
        levels = cls.build_tree(leaf_hashes)
        return levels[-1][0]

    @classmethod
    def generate_proof(cls, leaf_hashes: list[str], leaf_index: int) -> list[dict[str, str]]:
        """
        Generate cryptographic Merkle inclusion audit path for a leaf at leaf_index.
        Each step contains:
          - position: "left" (sibling is on left, hash sibling + current)
                      or "right" (sibling is on right, hash current + sibling)
          - hash: sibling hash
        """
        if not leaf_hashes or leaf_index < 0 or leaf_index >= len(leaf_hashes):
            return []

        if len(leaf_hashes) == 1:
            return []

        levels = cls.build_tree(leaf_hashes)
        audit_path: list[dict[str, str]] = []
        current_idx = leaf_index

        for level_idx in range(len(levels) - 1):
            level = levels[level_idx]
            # Handle duplication if level was odd
            if len(level) % 2 != 0:
                level = list(level) + [level[-1]]

            is_right_child = current_idx % 2 == 1
            sibling_idx = current_idx - 1 if is_right_child else current_idx + 1

            if sibling_idx < len(level):
                sibling_hash = level[sibling_idx]
                audit_path.append(
                    {
                        "position": "left" if is_right_child else "right",
                        "hash": sibling_hash,
                    }
                )

            current_idx = current_idx // 2

        return audit_path

    @classmethod
    def verify_proof(
        cls,
        leaf_hash: str,
        audit_path: list[dict[str, str]],
        expected_root: str,
    ) -> bool:
        """
        Verify that a leaf hash is part of the Merkle tree with root expected_root.
        Zero-knowledge proof: verifies without inspecting other entries.
        """
        if not audit_path:
            return leaf_hash.lower() == expected_root.lower()

        current = leaf_hash
        for step in audit_path:
            sibling = step.get("hash", "")
            position = step.get("position", "right")

            if position == "left":
                current = cls.hash_nodes(sibling, current)
            else:
                current = cls.hash_nodes(current, sibling)

        return current.lower() == expected_root.lower()

    @classmethod
    async def compute_workspace_merkle_root(
        cls,
        db: AsyncSession,
        workspace_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        action_filter: str | None = None,
    ) -> MerkleAuditRootResponse:
        """Compute the Merkle Root across recorded audit events matching filters."""
        stmt = select(AuditEvent).order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
        if workspace_id:
            stmt = stmt.where(AuditEvent.workspace_id == workspace_id)
        if start_date:
            stmt = stmt.where(AuditEvent.created_at >= start_date)
        if end_date:
            stmt = stmt.where(AuditEvent.created_at <= end_date)
        if action_filter:
            stmt = stmt.where(AuditEvent.action == action_filter)

        events = list((await db.execute(stmt)).scalars().all())
        now_dt = datetime.now(UTC)

        if not events:
            empty_root = hashlib.sha256(b"empty_root").hexdigest()
            return MerkleAuditRootResponse(
                merkle_root=empty_root,
                total_leaves=0,
                tree_depth=0,
                workspace_id=workspace_id,
                generated_at=now_dt,
            )

        leaf_hashes = [cls.hash_leaf(e) for e in events]
        levels = cls.build_tree(leaf_hashes)
        root = levels[-1][0]

        return MerkleAuditRootResponse(
            merkle_root=root,
            total_leaves=len(events),
            tree_depth=len(levels),
            workspace_id=workspace_id,
            generated_at=now_dt,
        )

    @classmethod
    async def generate_event_inclusion_proof(
        cls,
        db: AsyncSession,
        event_id: str,
        workspace_id: str | None = None,
    ) -> MerkleProofResponse | None:
        """
        Generate Merkle inclusion proof for a single audit event within the workspace audit trail.
        """
        stmt = select(AuditEvent).order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
        if workspace_id:
            stmt = stmt.where(AuditEvent.workspace_id == workspace_id)

        events = list((await db.execute(stmt)).scalars().all())
        target_idx: int | None = None
        target_event: AuditEvent | None = None

        for idx, evt in enumerate(events):
            if evt.id == event_id:
                target_idx = idx
                target_event = evt
                break

        if target_idx is None or target_event is None:
            return None

        leaf_hashes = [cls.hash_leaf(e) for e in events]
        audit_path = cls.generate_proof(leaf_hashes, target_idx)
        root = cls.get_merkle_root(leaf_hashes)
        target_leaf_hash = leaf_hashes[target_idx]

        return MerkleProofResponse(
            event_id=target_event.id,
            action=target_event.action,
            leaf_hash=target_leaf_hash,
            leaf_index=target_idx,
            merkle_root=root,
            total_leaves=len(events),
            audit_path=audit_path,
            generated_at=datetime.now(UTC),
        )

    @classmethod
    def verify_inclusion_proof(
        cls,
        leaf_hash: str,
        merkle_root: str,
        audit_path: list[dict[str, str]],
    ) -> MerkleProofVerificationResponse:
        """Verify Merkle proof and return structured attestation response."""
        now_dt = datetime.now(UTC)

        if not audit_path:
            is_valid = leaf_hash.lower() == merkle_root.lower()
            return MerkleProofVerificationResponse(
                is_valid=is_valid,
                computed_root=leaf_hash,
                expected_root=merkle_root,
                message=(
                    "Single-node tree proof verified."
                    if is_valid
                    else "Leaf hash does not match root."
                ),
                verified_at=now_dt,
            )

        current = leaf_hash
        for step in audit_path:
            sibling = step.get("hash", "")
            position = step.get("position", "right")
            if position == "left":
                current = cls.hash_nodes(sibling, current)
            else:
                current = cls.hash_nodes(current, sibling)

        is_valid = current.lower() == merkle_root.lower()
        msg = (
            "Cryptographic Merkle inclusion proof verified successfully. Event is certified in state root."
            if is_valid
            else "Merkle inclusion proof verification failed. Computed root differs from expected root."
        )

        return MerkleProofVerificationResponse(
            is_valid=is_valid,
            computed_root=current,
            expected_root=merkle_root,
            message=msg,
            verified_at=now_dt,
        )
