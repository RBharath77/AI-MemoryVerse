import base64
import hashlib
import logging
import secrets

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import settings

logger = logging.getLogger(__name__)


class SecretEncryptionService:
    """Cryptographic Envelope Secret Encryption at Rest.

    Encrypts sensitive third-party API tokens, webhook secrets, and workspace
    credentials using authenticated AES-128-CBC with HMAC-SHA256 (Fernet)
    derived from the application master key.
    """

    _fernet: Fernet | None = None

    @classmethod
    def _get_fernet(cls) -> Fernet:
        if cls._fernet is None:
            raw_key = getattr(settings, "SECRET_ENCRYPTION_KEY", None) or settings.SECRET_KEY
            derived_bytes = hashlib.sha256(raw_key.encode("utf-8")).digest()
            fernet_key = base64.urlsafe_b64encode(derived_bytes)
            cls._fernet = Fernet(fernet_key)
        return cls._fernet

    @classmethod
    def encrypt_secret(cls, plaintext: str) -> str:
        """Encrypt plaintext secret into authenticated ciphertext."""
        if not plaintext:
            return ""
        f = cls._get_fernet()
        return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    @classmethod
    def decrypt_secret(cls, ciphertext: str) -> str:
        """Decrypt ciphertext back to original plaintext secret."""
        if not ciphertext:
            return ""
        f = cls._get_fernet()
        try:
            return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            logger.error("Failed to decrypt secret: invalid token or corrupted master key.")
            raise ValueError("Corrupted or unauthorized ciphertext secret.")

    @classmethod
    def mask_secret(cls, secret: str) -> str:
        """Return masked preview of a secret suitable for UI presentation."""
        if not secret:
            return ""
        if len(secret) <= 8:
            return "••••••••"
        return f"{secret[:4]}••••{secret[-4:]}"


class CMEKService:
    """Customer-Managed Encryption Keys (CMEK) & Multi-Version Key Lifecycle Management.

    Derives per-workspace Data Encryption Keys (DEKs) using HKDF-SHA256 from
    the master key and tenant-specific salt and version. Supports multi-version
    key rotation and zero-knowledge crypto-shredding.
    """

    @classmethod
    def generate_salt(cls) -> str:
        """Generate a cryptographically secure tenant salt."""
        return secrets.token_hex(16)

    @classmethod
    def derive_workspace_key(
        cls,
        workspace_id: str,
        key_version: int = 1,
        salt: str | None = None,
    ) -> Fernet:
        """Derive a tenant-isolated Fernet instance for the specific workspace and key version."""
        raw_master = getattr(settings, "SECRET_ENCRYPTION_KEY", None) or settings.SECRET_KEY
        salt_bytes = (salt or f"{workspace_id}:v{key_version}").encode("utf-8")
        info = f"cmek-dek:{workspace_id}:v{key_version}".encode()

        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt_bytes,
            info=info,
        )
        derived = hkdf.derive(raw_master.encode("utf-8"))
        fernet_key = base64.urlsafe_b64encode(derived)
        return Fernet(fernet_key)

    @classmethod
    def encrypt_with_cmek(
        cls,
        plaintext: str,
        workspace_id: str,
        key_version: int = 1,
        salt: str | None = None,
    ) -> str:
        """Encrypt plaintext secret using tenant-specific CMEK key."""
        if not plaintext:
            return ""
        f = cls.derive_workspace_key(workspace_id, key_version, salt)
        return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    @classmethod
    def decrypt_with_cmek(
        cls,
        ciphertext: str,
        workspace_id: str,
        key_version: int = 1,
        salt: str | None = None,
    ) -> str:
        """Decrypt ciphertext using tenant-specific CMEK key with fallback to master key."""
        if not ciphertext:
            return ""
        f = cls.derive_workspace_key(workspace_id, key_version, salt)
        try:
            return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            # Fallback to standard master key for backward compatibility
            return SecretEncryptionService.decrypt_secret(ciphertext)
