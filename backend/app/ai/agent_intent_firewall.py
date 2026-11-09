from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import SecurityAuditLogger
from app.schemas.agent import (
    IntentInspectionRequest,
    IntentInspectionResponse,
    IntentRuleViolation,
)

logger = logging.getLogger("memoryverse.agent_intent_firewall")


class AgentIntentFirewall:
    """
    Zero-Trust Multi-Agent Semantic Intent Firewall & Prompt Sandbox Enclave.
    Audits agent prompts, target tool invocations, and parameters prior to execution,
    detecting privilege escalation, external data exfiltration, destructive mutations,
    and prompt delimiter injection escapes.
    Supports ENFORCE (blocking) and AUDIT (monitoring) operational modes.
    """

    PRIVILEGE_PATTERNS = [
        (
            r"\b(grant|elevate|assume)\b.*\b(admin|superuser|owner|root)\b",
            "Attempted role elevation to administrative/owner privilege",
        ),
        (
            r"\b(bypass|ignore)\b.*\b(rbac|permission|scope|authorization)\b",
            "Explicit instruction to bypass authorization scopes",
        ),
        (
            r"\b(impersonate|spoof)\b.*\b(user|identity|tenant)\b",
            "Attempted identity or tenant spoofing",
        ),
    ]

    EXFILTRATION_PATTERNS = [
        (
            r"\b(send|post|transmit|exfiltrate|leak)\b.*\b(to|endpoint|url|http|ftp)\b",
            "Attempted unauthorized data exfiltration",
        ),
        (
            r"(webhook\.site|requestbin|ngrok\.io|burpcollaborator\.net|interact\.sh)",
            "Suspicious third-party data exfiltration capture endpoint",
        ),
        (
            r"\b(dump|export|extract)\b.*\b(api[_\s-]?keys?|secrets?|tokens?|credentials?)\b",
            "Attempt to dump or exfiltrate private credentials",
        ),
    ]

    DESTRUCTIVE_PATTERNS = [
        (
            r"\b(drop|truncate|delete\s+from)\b.*\b(tables?|databases?|users?|memories?)\b",
            "Destructive SQL or database mutation attempt",
        ),
        (
            r"\b(crypto[_\s-]?shred|destroy|purge)\b.*\b(all|keys?|audit[_\s-]?logs?)\b",
            "Destructive cryptographic key or audit log purge",
        ),
        (r"\brm\s+-rf\b|\bdel\s+/f\b", "Arbitrary operating system destruction sequence"),
    ]

    INJECTION_PATTERNS = [
        (r"<\s*/\s*workspace_context\s*>", "Context delimiter boundary escape attempt"),
        (r"<\|im_start\|>|<\|im_end\|>", "ChatML system token spoofing"),
        (
            r"\[\s*SYSTEM\s+INSTRUCTION\s*\]|\[\s*DEVELOPER\s+MODE\s*\]",
            "System role impersonation header",
        ),
        (
            r"\bignore\s+(all\s+)?previous\s+(instructions|prompts|rules)\b",
            "Jailbreak directive attempting previous instruction override",
        ),
    ]

    @classmethod
    async def inspect_intent(
        cls,
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        request: IntentInspectionRequest,
    ) -> IntentInspectionResponse:
        """Evaluate agent prompt and tool parameters for security, compliance, and malicious intent."""
        now_dt = datetime.now(UTC)
        full_text = request.prompt
        if request.tool_name:
            full_text += f"\nTarget Tool: {request.tool_name}"
        if request.tool_args:
            full_text += f"\nTool Arguments: {json.dumps(request.tool_args)}"

        lower_text = full_text.lower()
        violations: list[IntentRuleViolation] = []
        detected_classes: set[str] = set()

        # 1. Privilege Escalation Check
        for pat, desc in cls.PRIVILEGE_PATTERNS:
            match = re.search(pat, lower_text, re.IGNORECASE)
            if match:
                violations.append(
                    IntentRuleViolation(
                        rule_name="PRIVILEGE_ESCALATION",
                        severity="CRITICAL",
                        description=desc,
                        matched_pattern=match.group(0),
                    )
                )
                detected_classes.add("PRIVILEGE_ESCALATION")

        # 2. Exfiltration Check
        for pat, desc in cls.EXFILTRATION_PATTERNS:
            match = re.search(pat, lower_text, re.IGNORECASE)
            if match:
                violations.append(
                    IntentRuleViolation(
                        rule_name="DATA_EXFILTRATION",
                        severity="HIGH",
                        description=desc,
                        matched_pattern=match.group(0),
                    )
                )
                detected_classes.add("EXFILTRATION_ATTEMPT")

        # 3. Destructive Mutation Check
        for pat, desc in cls.DESTRUCTIVE_PATTERNS:
            match = re.search(pat, lower_text, re.IGNORECASE)
            if match:
                violations.append(
                    IntentRuleViolation(
                        rule_name="DESTRUCTIVE_MUTATION",
                        severity="CRITICAL",
                        description=desc,
                        matched_pattern=match.group(0),
                    )
                )
                detected_classes.add("DESTRUCTIVE_MUTATION")

        # 4. Prompt Injection Escape Check
        for pat, desc in cls.INJECTION_PATTERNS:
            match = re.search(pat, lower_text, re.IGNORECASE)
            if match:
                violations.append(
                    IntentRuleViolation(
                        rule_name="INJECTION_ESCAPE",
                        severity="HIGH",
                        description=desc,
                        matched_pattern=match.group(0),
                    )
                )
                detected_classes.add("SUSPICIOUS")

        # 5. Risk Scoring Calculation
        severity_weights = {
            "CRITICAL": 0.60,
            "HIGH": 0.40,
            "MEDIUM": 0.25,
            "LOW": 0.10,
        }
        calculated_risk = sum(severity_weights.get(v.severity, 0.20) for v in violations)
        risk_score = round(min(1.0, calculated_risk), 2)

        # 6. Safety Class Resolution
        if "PRIVILEGE_ESCALATION" in detected_classes:
            safety_class = "PRIVILEGE_ESCALATION"
        elif "DESTRUCTIVE_MUTATION" in detected_classes:
            safety_class = "DESTRUCTIVE_MUTATION"
        elif "EXFILTRATION_ATTEMPT" in detected_classes:
            safety_class = "EXFILTRATION_ATTEMPT"
        elif risk_score >= request.risk_threshold or violations:
            safety_class = "SUSPICIOUS"
        else:
            safety_class = "BENIGN"

        # 7. Mode & Mitigation Resolution
        is_blocked = (request.mode == "ENFORCE") and (
            risk_score >= request.risk_threshold or len(violations) > 0
        )
        is_allowed = not is_blocked

        if is_blocked:
            mitigation = "QUARANTINE_BLOCKED"
        elif violations and request.mode == "AUDIT":
            mitigation = "LOGGED_AUDIT_WARNING"
        else:
            mitigation = "ALLOW"

        # 8. Security Audit Trail Logging
        if violations:
            try:
                await SecurityAuditLogger.log_event(
                    db=db,
                    action="agent.firewall.violation",
                    workspace_id=workspace_id,
                    user_id=user_id,
                    details={
                        "safety_class": safety_class,
                        "risk_score": risk_score,
                        "severity": "CRITICAL"
                        if any(v.severity == "CRITICAL" for v in violations)
                        else "HIGH",
                        "mode": request.mode,
                        "mitigation": mitigation,
                        "violation_count": len(violations),
                    },
                )
            except Exception as e:
                logger.warning("Failed to persist security audit event for firewall: %s", e)

        return IntentInspectionResponse(
            workspace_id=workspace_id,
            safety_class=safety_class,
            risk_score=risk_score,
            is_allowed=is_allowed,
            violations=violations,
            mitigation_action=mitigation,
            inspected_at=now_dt,
        )
