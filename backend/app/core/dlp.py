from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("memoryverse.dlp")


@dataclass
class DLPInspectionResult:
    original_text: str
    sanitized_text: str
    is_clean: bool
    violations: list[str] = field(default_factory=list)
    action: str = "REDACT"
    blocked: bool = False


class WorkspaceDLPService:
    """Enterprise Data Loss Prevention (DLP) engine enforcing workspace-level redaction, tokenization, or blocking."""

    STANDARD_RULES: dict[str, tuple[re.Pattern, str]] = {
        "CREDIT_CARD": (
            re.compile(
                r"\b(?:\d{4}[-\s]?){3}\d{4}\b|\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b"
            ),
            "[REDACTED_CREDIT_CARD]",
        ),
        "SSN": (
            re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
            "[REDACTED_SSN]",
        ),
        "API_KEY": (
            re.compile(r"\b(?:sk-[a-zA-Z0-9_\-]{20,}|AKIA[0-9A-Z]{16}|ghp_[a-zA-Z0-9]{36})\b"),
            "[REDACTED_API_KEY]",
        ),
        "EMAIL": (
            re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
            "[REDACTED_EMAIL]",
        ),
        "PHONE": (
            re.compile(r"\b(?:\+?1[-. ]?)?\(?[0-9]{3}\)?[-. ]?[0-9]{3}[-. ]?[0-9]{4}\b"),
            "[REDACTED_PHONE]",
        ),
    }

    @classmethod
    def inspect(cls, text: str, policy: dict[str, Any] | None) -> DLPInspectionResult:
        """Inspect and sanitize text according to workspace DLP policy settings."""
        if not text or not policy or not policy.get("enabled", False):
            return DLPInspectionResult(
                original_text=text,
                sanitized_text=text,
                is_clean=True,
                violations=[],
                action="ALLOW",
                blocked=False,
            )

        action = str(policy.get("action", "REDACT")).upper()
        active_rules = policy.get("active_rules", ["CREDIT_CARD", "SSN", "API_KEY"])
        custom_rules = policy.get("custom_rules", [])

        sanitized = text
        violations: list[str] = []

        # 1. Apply active standard rules
        for rule_key in active_rules:
            if rule_key in cls.STANDARD_RULES:
                pattern, replacement = cls.STANDARD_RULES[rule_key]
                if pattern.search(sanitized):
                    violations.append(rule_key)
                    if action == "REDACT":
                        sanitized = pattern.sub(replacement, sanitized)

        # 2. Apply custom regex rules
        if isinstance(custom_rules, list):
            for cr in custom_rules:
                if isinstance(cr, dict) and "pattern" in cr:
                    try:
                        c_pat = re.compile(cr["pattern"])
                        c_name = cr.get("name", "CUSTOM_RULE")
                        c_rep = cr.get("replacement", "[REDACTED_CONFIDENTIAL]")
                        if c_pat.search(sanitized):
                            violations.append(c_name)
                            if action == "REDACT":
                                sanitized = c_pat.sub(c_rep, sanitized)
                    except re.error:
                        pass

        is_clean = len(violations) == 0
        blocked = action == "BLOCK" and not is_clean

        if not is_clean:
            logger.info(
                "DLP Policy triggered: action=%s blocked=%s violations=%s",
                action,
                blocked,
                violations,
            )

        return DLPInspectionResult(
            original_text=text,
            sanitized_text=sanitized if action == "REDACT" else text,
            is_clean=is_clean,
            violations=violations,
            action=action,
            blocked=blocked,
        )
