import hashlib
import hmac
import logging
import time

logger = logging.getLogger(__name__)


class WebhookSignatureService:
    """
    Cryptographic HMAC-SHA256 signature service for outgoing webhooks.
    Allows recipient webhooks to verify payload integrity and origin,
    while defeating replay attacks via bounded timestamp windows.
    """

    DEFAULT_TOLERANCE_SECONDS: int = 300  # 5 minutes

    @classmethod
    def sign_payload(
        cls,
        payload_bytes: bytes,
        secret: str,
        timestamp: int | None = None,
    ) -> tuple[str, int]:
        """
        Sign outgoing payload bytes with HMAC-SHA256.
        Returns:
            (signature_header_string, timestamp)
            e.g. ("t=1731070000,v1=9f86d081884c7d65...", 1731070000)
        """
        ts = int(time.time()) if timestamp is None else timestamp
        signature_base = f"{ts}.".encode() + payload_bytes
        mac = hmac.new(secret.encode("utf-8"), signature_base, hashlib.sha256).hexdigest()
        header_val = f"t={ts},v1={mac}"
        return header_val, ts

    @classmethod
    def verify_signature(
        cls,
        payload_bytes: bytes,
        header_value: str,
        secret: str,
        tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS,
    ) -> bool:
        """
        Verify incoming webhook signature header against secret and payload.
        Enforces constant-time comparison and timestamp freshness check.
        """
        if not header_value or not secret:
            return False

        try:
            parts = dict(item.strip().split("=", 1) for item in header_value.split(","))
            ts_str = parts.get("t")
            v1_sig = parts.get("v1")

            if not ts_str or not v1_sig or not ts_str.isdigit():
                return False

            timestamp = int(ts_str)
            now = int(time.time())

            # Anti-Replay check: timestamp must be within tolerance window
            if abs(now - timestamp) > tolerance_seconds:
                logger.warning(
                    f"Webhook timestamp outside tolerance window ({abs(now - timestamp)}s > {tolerance_seconds}s)"
                )
                return False

            # Compute expected HMAC
            signature_base = f"{timestamp}.".encode() + payload_bytes
            expected_mac = hmac.new(
                secret.encode("utf-8"), signature_base, hashlib.sha256
            ).hexdigest()

            # Constant-time comparison to defeat timing attacks
            return hmac.compare_digest(v1_sig, expected_mac)
        except Exception as e:
            logger.error(f"Error validating webhook signature: {e}")
            return False
