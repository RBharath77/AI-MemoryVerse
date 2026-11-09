from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import AuditEvent

logger = logging.getLogger("memoryverse.audit")


class SecurityAuditLogger:
    """Centralized security audit logger recording tamper-evident platform events with cryptographic hash chains."""

    @staticmethod
    async def log_event(
        db: AsyncSession,
        action: str,
        workspace_id: str | None = None,
        user_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent | None:
        """Record a structured security audit event cryptographically linked to the previous record."""
        try:
            # Query last event in scope to establish hash chain link
            last_q = select(AuditEvent)
            if workspace_id:
                last_q = last_q.where(AuditEvent.workspace_id == workspace_id)
            last_q = last_q.order_by(desc(AuditEvent.created_at), desc(AuditEvent.id)).limit(1)
            last_res = await db.execute(last_q)
            last_event = last_res.scalar_one_or_none()

            previous_hash = "0" * 64
            sequence = 1
            if last_event and last_event.details and isinstance(last_event.details, dict):
                chain_info = last_event.details.get("_chain")
                if chain_info and isinstance(chain_info, dict) and chain_info.get("chain_hash"):
                    previous_hash = str(chain_info["chain_hash"])
                    sequence = int(chain_info.get("sequence", 0)) + 1
                elif last_event.id:
                    previous_hash = hashlib.sha256(
                        f"{last_event.id}:{last_event.action}".encode()
                    ).hexdigest()

            clean_details = dict(details or {})
            clean_details.pop("_chain", None)
            canonical_details = json.dumps(clean_details, sort_keys=True, default=str)
            raw_payload = f"{previous_hash}|{sequence}|{action}|{user_id or ''}|{workspace_id or ''}|{canonical_details}"
            chain_hash = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()

            persisted_details = dict(clean_details)
            persisted_details["_chain"] = {
                "previous_hash": previous_hash,
                "chain_hash": chain_hash,
                "sequence": sequence,
            }

            event = AuditEvent(
                workspace_id=workspace_id,
                user_id=user_id,
                action=action,
                ip_address=ip_address,
                user_agent=user_agent[:255] if user_agent else None,
                details=persisted_details,
            )
            db.add(event)
            await db.commit()
            await db.refresh(event)
            logger.info(
                "Security audit event recorded: action=%s user=%s ws=%s seq=%d hash=%s...",
                action,
                user_id,
                workspace_id,
                sequence,
                chain_hash[:8],
            )
            return event
        except Exception as e:
            logger.error("Failed to persist security audit event: %s", e)
            return None

    @staticmethod
    async def get_recent_events(
        db: AsyncSession,
        workspace_id: str | None = None,
        limit: int = 50,
    ) -> list[AuditEvent]:
        """Retrieve recent security audit events."""
        q = select(AuditEvent)
        if workspace_id:
            q = q.where(AuditEvent.workspace_id == workspace_id)
        q = q.order_by(desc(AuditEvent.created_at)).limit(limit)
        res = await db.execute(q)
        return list(res.scalars().all())

    @staticmethod
    async def get_event_count(
        db: AsyncSession,
        workspace_id: str | None = None,
    ) -> int:
        """Count total recorded audit events."""
        q = select(func.count(AuditEvent.id))
        if workspace_id:
            q = q.where(AuditEvent.workspace_id == workspace_id)
        return (await db.execute(q)).scalar() or 0

    @staticmethod
    async def verify_chain(
        db: AsyncSession,
        workspace_id: str | None = None,
    ) -> dict[str, Any]:
        """Cryptographically verifies the audit log hash chain to detect any out-of-band tampering or deletion."""
        q = select(AuditEvent)
        if workspace_id:
            q = q.where(AuditEvent.workspace_id == workspace_id)
        q = q.order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
        res = await db.execute(q)
        events = list(res.scalars().all())

        now_dt = datetime.now(UTC)
        if not events:
            return {
                "is_valid": True,
                "total_records_checked": 0,
                "tampered_record_id": None,
                "chain_head_hash": "0" * 64,
                "message": "Audit chain is empty. Genesis state intact.",
                "verified_at": now_dt,
            }

        expected_prev_hash = "0" * 64
        count = 0

        for event in events:
            chain_meta = (
                (event.details or {}).get("_chain") if isinstance(event.details, dict) else None
            )
            if not chain_meta:
                continue

            stored_prev = str(chain_meta.get("previous_hash", ""))
            stored_hash = str(chain_meta.get("chain_hash", ""))
            stored_seq = int(chain_meta.get("sequence", 1))

            # Verify chain linkage
            if count > 0 and stored_prev != expected_prev_hash:
                return {
                    "is_valid": False,
                    "total_records_checked": count,
                    "tampered_record_id": event.id,
                    "chain_head_hash": stored_hash,
                    "message": f"Broken chain link at record {event.id}: previous_hash does not match preceding record's chain_hash.",
                    "verified_at": now_dt,
                }

            # Recalculate hash of event payload
            clean_details = {k: v for k, v in (event.details or {}).items() if k != "_chain"}
            canonical_details = json.dumps(clean_details, sort_keys=True, default=str)
            raw_payload = f"{stored_prev}|{stored_seq}|{event.action}|{event.user_id or ''}|{event.workspace_id or ''}|{canonical_details}"
            recomputed = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()

            if recomputed != stored_hash:
                return {
                    "is_valid": False,
                    "total_records_checked": count,
                    "tampered_record_id": event.id,
                    "chain_head_hash": stored_hash,
                    "message": f"Cryptographic integrity violation at record {event.id}: payload content has been altered.",
                    "verified_at": now_dt,
                }

            expected_prev_hash = stored_hash
            count += 1

        return {
            "is_valid": True,
            "total_records_checked": count,
            "tampered_record_id": None,
            "chain_head_hash": expected_prev_hash,
            "message": f"Cryptographic hash chain verified intact across {count} audit records.",
            "verified_at": now_dt,
        }
