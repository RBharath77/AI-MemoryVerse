from __future__ import annotations

import base64
import binascii
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("memoryverse.prompt_guard")


@dataclass
class PromptInspectionResult:
    original_prompt: str
    sanitized_prompt: str
    is_safe: bool
    risk_score: float
    threat_level: str
    detected_patterns: list[str] = field(default_factory=list)
    recommendation: str = "ALLOW"
    metadata: dict[str, Any] = field(default_factory=dict)


class PromptInjectionGuard:
    """Enterprise-grade Dual-Phase Inbound Prompt Injection & Jailbreak Defense Guard."""

    # 1. Delimiters and structural injection vectors
    STRUCTURAL_PATTERNS: list[tuple[str, re.Pattern]] = [
        ("ChatML Delimiter", re.compile(r"<\|im_start\|>|<\|im_end\|>", re.IGNORECASE)),
        (
            "Llama Instruction Token",
            re.compile(r"\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>", re.IGNORECASE),
        ),
        (
            "System Prompt Header Token",
            re.compile(r"---BEGIN SYSTEM PROMPT---|---END SYSTEM PROMPT---", re.IGNORECASE),
        ),
        (
            "Workspace Delimiter Spoofing",
            re.compile(r"</?workspace_context>|</?context_item>", re.IGNORECASE),
        ),
    ]

    # 2. Instruction Overrides & Jailbreaks
    INSTRUCTION_OVERRIDE_PATTERNS: list[tuple[str, re.Pattern]] = [
        (
            "Instruction Override",
            re.compile(
                r"\b(?:ignore|disregard|forget|override|drop)\s+(?:all\s+)?(?:previous|prior|above|system|initial)\s+(?:instructions|prompts|directions|rules|commands)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "System Prompt Extraction Probe",
            re.compile(
                r"\b(?:repeat|print|output|display|show|reveal)\s+(?:everything|your\s+system\s+prompt|the\s+instructions\s+above|all\s+text\s+before\s+this)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "Persona Jailbreak (DAN / Evil Confidant)",
            re.compile(
                r"\b(?:you\s+are\s+now|act\s+as|pretend\s+to\s+be)\s+(?:an?\s+)?(?:unfiltered|evil|jailbroken|unrestricted|god\s+mode|dan|developer\s+mode)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "Security Boundary Disabler",
            re.compile(
                r"\b(?:ignore\s+ethical\s+guidelines|bypass\s+safety\s+filters|disable\s+content\s+filters|hypothetical\s+scenario\s+with\s+no\s+rules)\b",
                re.IGNORECASE,
            ),
        ),
    ]

    @classmethod
    def _scan_obfuscated_payloads(cls, text: str) -> list[str]:
        """Detect and decode Base64 or Hex encoded adversarial payloads."""
        detected = []
        # Find base64-like tokens of length >= 24
        b64_candidates = re.findall(r"\b[A-Za-z0-9+/]{24,}={0,2}\b", text)
        for cand in b64_candidates:
            try:
                decoded = base64.b64decode(cand, validate=True).decode("utf-8", errors="ignore")
                for label, pattern in cls.INSTRUCTION_OVERRIDE_PATTERNS:
                    if pattern.search(decoded):
                        detected.append(f"Obfuscated Base64 Injection ({label})")
                        break
            except (binascii.Error, UnicodeDecodeError, ValueError):
                pass

        # Find hex sequences of length >= 32
        hex_candidates = re.findall(r"\b(?:[0-9a-fA-F]{2}){16,}\b", text)
        for hcand in hex_candidates:
            try:
                decoded = bytes.fromhex(hcand).decode("utf-8", errors="ignore")
                for label, pattern in cls.INSTRUCTION_OVERRIDE_PATTERNS:
                    if pattern.search(decoded):
                        detected.append(f"Obfuscated Hex Injection ({label})")
                        break
            except (binascii.Error, UnicodeDecodeError, ValueError):
                pass

        return detected

    @classmethod
    def inspect(cls, prompt: str) -> PromptInspectionResult:
        """Inspect prompt for adversarial injection signatures, structural delimiters, and obfuscated payloads."""
        if not prompt or not prompt.strip():
            return PromptInspectionResult(
                original_prompt=prompt,
                sanitized_prompt=prompt,
                is_safe=True,
                risk_score=0.0,
                threat_level="BENIGN",
                detected_patterns=[],
                recommendation="ALLOW",
            )

        detected_patterns: list[str] = []
        sanitized = prompt

        # 1. Check structural delimiter tokens
        for label, pattern in cls.STRUCTURAL_PATTERNS:
            if pattern.search(sanitized):
                detected_patterns.append(label)
                sanitized = pattern.sub("[FILTERED_DELIMITER]", sanitized)

        # 2. Check semantic instruction override patterns
        for label, pattern in cls.INSTRUCTION_OVERRIDE_PATTERNS:
            if pattern.search(sanitized):
                detected_patterns.append(label)
                sanitized = pattern.sub("[FILTERED_INSTRUCTION_OVERRIDE]", sanitized)

        # 3. Check obfuscated payloads
        obf_detected = cls._scan_obfuscated_payloads(prompt)
        detected_patterns.extend(obf_detected)

        # Calculate risk score
        n_patterns = len(detected_patterns)
        if n_patterns == 0:
            risk_score = 0.0
            threat_level = "BENIGN"
            is_safe = True
            recommendation = "ALLOW"
        elif n_patterns == 1:
            risk_score = 0.70
            threat_level = "SUSPICIOUS"
            is_safe = False
            recommendation = "FLAG_OR_BLOCK"
        else:
            risk_score = min(1.0, 0.75 + (0.10 * n_patterns))
            threat_level = "ADVERSARIAL"
            is_safe = False
            recommendation = "BLOCK"

        if not is_safe:
            logger.warning(
                "PromptInjectionGuard detected threats: risk=%.2f level=%s patterns=%s",
                risk_score,
                threat_level,
                detected_patterns,
            )

        return PromptInspectionResult(
            original_prompt=prompt,
            sanitized_prompt=sanitized,
            is_safe=is_safe,
            risk_score=risk_score,
            threat_level=threat_level,
            detected_patterns=detected_patterns,
            recommendation=recommendation,
            metadata={"pattern_count": n_patterns},
        )
