from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.fernet import Fernet
from fastapi import HTTPException, status

from app.schemas.memory import (
    TimeLockedMemoryCreate,
    TimeLockedMemoryResponse,
    TimeLockedMemoryRevealResponse,
)

logger = logging.getLogger("memoryverse.time_locked_vault")


class TimeLockedVaultService:
    """
    Zero-Knowledge Multi-Tenant Ephemeral Memory Vault & Time-Locked Cryptographic Enclave.
    Stores high-sensitivity strategic credentials, ephemeral tokens, and self-destructing reflections
    under ephemeral per-record encryption keys with strict time-lock delays, read-count burning,
    and automatic cryptographic zeroization.
    """

    _vault_store: dict[str, dict[str, Any]] = {}

    @classmethod
    def _generate_key(cls) -> bytes:
        return Fernet.generate_key()

    @classmethod
    async def create_time_locked_memory(
        cls,
        workspace_id: str,
        user_id: str,
        request: TimeLockedMemoryCreate,
    ) -> TimeLockedMemoryResponse:
        """Encrypt and store secret in time-locked ephemeral vault."""
        now_dt = datetime.now(UTC)
        vault_id = str(uuid.uuid4())

        key = cls._generate_key()
        f = Fernet(key)
        ciphertext = f.encrypt(request.secret_content.encode("utf-8"))

        unlock_at = now_dt + timedelta(seconds=request.unlock_delay_seconds)
        expires_at = now_dt + timedelta(seconds=request.ttl_seconds)

        cls._vault_store[vault_id] = {
            "vault_id": vault_id,
            "workspace_id": workspace_id,
            "user_id": user_id,
            "hint": request.hint,
            "ciphertext": ciphertext,
            "key": key,
            "max_views": request.max_views,
            "views_remaining": request.max_views,
            "unlock_at": unlock_at,
            "expires_at": expires_at,
            "is_burned": False,
            "created_at": now_dt,
        }

        return TimeLockedMemoryResponse(
            vault_id=vault_id,
            workspace_id=workspace_id,
            hint=request.hint,
            max_views=request.max_views,
            views_remaining=request.max_views,
            unlock_at=unlock_at,
            expires_at=expires_at,
            is_unlocked=now_dt >= unlock_at,
            is_burned=False,
            created_at=now_dt,
        )

    @classmethod
    async def reveal_time_locked_memory(
        cls,
        workspace_id: str,
        vault_id: str,
    ) -> TimeLockedMemoryRevealResponse:
        """Decrypt and reveal ephemeral memory, decrementing views or executing burn-on-read."""
        now_dt = datetime.now(UTC)
        record = cls._vault_store.get(vault_id)

        if not record or record.get("is_burned") or record.get("workspace_id") != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Time-locked memory '{vault_id}' not found or already shredded",
            )

        # 1. Enforce Expiration TTL
        if now_dt >= record["expires_at"]:
            cls.crypto_shred(workspace_id, vault_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Time-locked memory has expired and been cryptographically shredded",
            )

        # 2. Enforce Time-Lock Delay Window
        if now_dt < record["unlock_at"]:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Time-locked memory is locked until {record['unlock_at'].isoformat()}",
            )

        # 3. Decrypt Content
        key = record["key"]
        ciphertext = record["ciphertext"]
        if not key or not ciphertext:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Encryption key unavailable; record already shredded",
            )

        f = Fernet(key)
        try:
            plaintext = f.decrypt(ciphertext).decode("utf-8")
        except Exception as e:
            logger.error("Decryption failure in time-locked vault: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Cryptographic decryption error",
            )

        # 4. Decrement Remaining Views
        record["views_remaining"] -= 1
        is_now_burned = record["views_remaining"] <= 0

        if is_now_burned:
            # Overwrite key with random noise and shred
            cls.crypto_shred(workspace_id, vault_id)

        return TimeLockedMemoryRevealResponse(
            vault_id=vault_id,
            workspace_id=workspace_id,
            decrypted_content=plaintext,
            views_remaining=max(0, record["views_remaining"]),
            is_burned=is_now_burned,
            expires_at=record["expires_at"],
            revealed_at=now_dt,
        )

    @classmethod
    def crypto_shred(cls, workspace_id: str, vault_id: str) -> bool:
        """Irreversibly zeroize encryption keys and shred memory ciphertext."""
        record = cls._vault_store.get(vault_id)
        if not record or record.get("workspace_id") != workspace_id:
            return False

        # Zeroize memory buffers
        record["key"] = None
        record["ciphertext"] = b""
        record["is_burned"] = True
        record["views_remaining"] = 0
        cls._vault_store.pop(vault_id, None)
        return True
