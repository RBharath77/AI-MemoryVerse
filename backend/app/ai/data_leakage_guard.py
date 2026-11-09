import logging
import re
from typing import NamedTuple

logger = logging.getLogger(__name__)


class LeakageInspectionResult(NamedTuple):
    sanitized_text: str
    is_clean: bool
    detected_leaks: list[str]


class DataLeakageGuard:
    """
    Zero-Trust Outbound Data Leakage Guard.
    Scans model completions and synthesized RAG answers before client transmission.
    Prevents cross-tenant UUID leaks, raw API credential exposure, and internal database stack trace disclosures.
    """

    CREDENTIAL_PATTERNS: list[tuple[str, re.Pattern, str]] = [
        ("OpenAI Key", re.compile(r"sk-[a-zA-Z0-9_\-]{20,}"), "[REDACTED_API_KEY]"),
        ("AWS Key", re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED_AWS_KEY]"),
        ("GitHub Token", re.compile(r"ghp_[a-zA-Z0-9]{36}"), "[REDACTED_GITHUB_TOKEN]"),
        ("Slack Token", re.compile(r"xox[baprs]-[0-9a-zA-Z\-]{10,}"), "[REDACTED_SLACK_TOKEN]"),
        (
            "JWT Token",
            re.compile(r"ey[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]+"),
            "[REDACTED_JWT]",
        ),
        (
            "Private Key",
            re.compile(
                r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
            ),
            "[REDACTED_PRIVATE_KEY]",
        ),
    ]

    DATABASE_ERROR_PATTERNS: list[tuple[str, re.Pattern, str]] = [
        (
            "Database Trace",
            re.compile(
                r"(?:psycopg2\.\w+Error|sqlalchemy\.exc\.\w+|SELECT\s+.*?\s+FROM\s+\w+|syntax error at or near\s+['\"])",
                re.IGNORECASE,
            ),
            "[SYSTEM_ERROR_FILTERED: Internal query trace suppressed for security]",
        )
    ]

    @classmethod
    def sanitize(
        cls,
        text: str,
        current_workspace_id: str,
        foreign_workspace_ids: list[str] | None = None,
    ) -> LeakageInspectionResult:
        if not text:
            return LeakageInspectionResult(sanitized_text="", is_clean=True, detected_leaks=[])

        sanitized = text
        detected: list[str] = []

        # 1. Foreign Workspace ID Isolation Check
        if foreign_workspace_ids:
            for f_id in foreign_workspace_ids:
                if f_id and f_id != current_workspace_id and f_id in sanitized:
                    detected.append(f"Foreign Workspace ID: {f_id}")
                    sanitized = sanitized.replace(f_id, "[REDACTED_TENANT_ID]")

        # 2. Secret & Credential Leakage Scanning
        for label, pattern, replacement in cls.CREDENTIAL_PATTERNS:
            matches = pattern.findall(sanitized)
            if matches:
                detected.append(label)
                sanitized = pattern.sub(replacement, sanitized)

        # 3. Database & SQL Stack Trace Redaction
        for label, pattern, replacement in cls.DATABASE_ERROR_PATTERNS:
            if pattern.search(sanitized):
                detected.append(label)
                sanitized = pattern.sub(replacement, sanitized)

        is_clean = len(detected) == 0
        if not is_clean:
            logger.warning(
                f"DataLeakageGuard intercepted leakage in workspace {current_workspace_id}: {detected}"
            )

        return LeakageInspectionResult(
            sanitized_text=sanitized,
            is_clean=is_clean,
            detected_leaks=detected,
        )
