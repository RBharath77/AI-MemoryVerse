import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
import urllib.parse
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings

# Argon2id password hasher with secure defaults
ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2id hash."""
    try:
        return ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, Exception):
        return False


def hash_token(token: str) -> str:
    """Create a SHA-256 hash of a refresh token to securely store in the database."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(
    subject: str,
    claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Generate a signed JWT access token."""
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "access",
    }
    if claims:
        payload.update(claims)

    encoded_jwt = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt


def create_refresh_token(
    subject: str,
    session_id: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Generate a signed JWT refresh token bound to a specific session_id."""
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    payload: dict[str, Any] = {
        "sub": subject,
        "sid": session_id,
        "jti": uuid.uuid4().hex,
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "refresh",
    }
    encoded_jwt = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt


def decode_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT token; returns payload dict or None if invalid/expired."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.PyJWTError:
        return None


def generate_totp_secret() -> str:
    """Generate a cryptographically secure 20-byte base32 TOTP secret."""
    random_bytes = os.urandom(20)
    return base64.b32encode(random_bytes).decode("ascii").replace("=", "")


def get_totp_uri(secret: str, account_name: str, issuer: str = "AI-MemoryVerse") -> str:
    """Generate an otpauth:// URI for authenticator app QR code scanning."""
    label = urllib.parse.quote(f"{issuer}:{account_name}")
    params = urllib.parse.urlencode(
        {"secret": secret, "issuer": issuer, "algorithm": "SHA1", "digits": 6, "period": 30}
    )
    return f"otpauth://totp/{label}?{params}"


def generate_totp_code(secret: str, time_step: int | None = None) -> str:
    """Generate the 6-digit TOTP code for a given secret at time_step."""
    if time_step is None:
        time_step = int(time.time() // 30)

    # Pad secret with '=' if necessary for base32 decoding
    padding = "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(secret.upper() + padding)

    # Pack counter as 8-byte big-endian integer
    counter_bytes = struct.pack(">Q", time_step)

    # Compute HMAC-SHA1
    mac = hmac.new(key, counter_bytes, hashlib.sha1).digest()

    # Dynamic truncation
    offset = mac[-1] & 0x0F
    code_int = struct.unpack(">I", mac[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code_int % 1000000).zfill(6)


def verify_totp_code(secret: str, code: str, window: int = 1) -> bool:
    """Verify a 6-digit TOTP code against a secret with +/- window steps tolerance."""
    if not code or len(code) != 6 or not code.isdigit():
        return False
    current_step = int(time.time() // 30)
    for offset in range(-window, window + 1):
        if generate_totp_code(secret, current_step + offset) == code:
            return True
    return False


def generate_mfa_backup_codes(count: int = 8) -> list[str]:
    """Generate cryptographically secure single-use backup recovery codes formatted as 'XXXX-XXXX'."""
    codes = []
    for _ in range(count):
        raw = secrets.token_hex(4).upper()
        formatted = f"{raw[:4]}-{raw[4:]}"
        codes.append(formatted)
    return codes


def hash_backup_code(code: str) -> str:
    """Normalize and compute SHA-256 hash of a backup recovery code."""
    cleaned = code.strip().replace("-", "").upper()
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
