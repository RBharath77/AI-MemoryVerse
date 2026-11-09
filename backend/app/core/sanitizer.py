from __future__ import annotations

import re
from typing import NamedTuple


class RedactionResult(NamedTuple):
    sanitized_text: str
    detected_types: list[str]


class CredentialSanitizer:
    """High-performance automated redaction engine for credentials, API tokens, and PII.

    Prevents sensitive keys from being embedded in long-term memories, vector embeddings,
    application logs, or third-party LLM prompt dispatches.
    """

    PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
        # OpenAI API Keys
        (
            "OPENAI_API_KEY",
            re.compile(r"\b(sk-(?:proj-)?[A-Za-z0-9_-]{20,})\b"),
            "[REDACTED_OPENAI_KEY]",
        ),
        # Google Gemini / Cloud API Keys
        (
            "GEMINI_API_KEY",
            re.compile(r"\b(AIzaSy[A-Za-z0-9_-]{33})\b"),
            "[REDACTED_GEMINI_KEY]",
        ),
        # AWS Access Key ID
        (
            "AWS_ACCESS_KEY",
            re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),
            "[REDACTED_AWS_KEY]",
        ),
        # GitHub Personal Access Token
        (
            "GITHUB_TOKEN",
            re.compile(r"\b(ghp_[A-Za-z0-9]{36})\b"),
            "[REDACTED_GITHUB_TOKEN]",
        ),
        # Slack API Token
        (
            "SLACK_TOKEN",
            re.compile(r"\b(xox[baprs]-[0-9A-Za-z-]{10,})\b"),
            "[REDACTED_SLACK_TOKEN]",
        ),
        # JWT / Bearer Tokens
        (
            "JWT_BEARER_TOKEN",
            re.compile(r"\b(eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})\b"),
            "[REDACTED_JWT_TOKEN]",
        ),
        # Credit Card Numbers (Visa, MasterCard, Amex, Discover)
        (
            "CREDIT_CARD",
            re.compile(
                r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b"
            ),
            "[REDACTED_CREDIT_CARD]",
        ),
        # US Social Security Number
        (
            "SSN",
            re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
            "[REDACTED_SSN]",
        ),
    ]

    @classmethod
    def redact(cls, text: str) -> RedactionResult:
        """Scan input text, replace sensitive matches with redaction tokens, and report findings."""
        if not text:
            return RedactionResult(sanitized_text=text, detected_types=[])

        sanitized = text
        detected: list[str] = []

        for name, pattern, replacement in cls.PATTERNS:
            if pattern.search(sanitized):
                detected.append(name)
                sanitized = pattern.sub(replacement, sanitized)

        return RedactionResult(sanitized_text=sanitized, detected_types=detected)
