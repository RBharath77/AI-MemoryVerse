from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

from app.schemas.document import (
    SchemaExtractionResponse,
    TargetJsonSchema,
)

logger = logging.getLogger("memoryverse.schema_extractor")


class CognitiveSchemaEngine:
    """Extracts strictly-typed structured JSON records from unstructured text validated against JSON schemas."""

    @classmethod
    def _coerce_type(cls, value: Any, target_type: str) -> tuple[Any, str | None]:
        """Attempt to coerce value into target_type. Returns (coerced_value, error_or_None)."""
        target_type = target_type.lower()

        if value is None:
            return None, "Value is None"

        if target_type == "string":
            return str(value).strip(), None

        if target_type in ("integer", "int"):
            try:
                if isinstance(value, (int, float)):
                    return int(value), None
                # Clean string
                clean = re.sub(r"[^\d\-+]", "", str(value))
                if clean:
                    return int(clean), None
            except Exception as e:
                return None, f"Failed to coerce '{value}' to integer: {e}"
            return None, f"Cannot convert '{value}' to integer"

        if target_type in ("number", "float"):
            try:
                if isinstance(value, (int, float)):
                    return float(value), None
                clean = re.sub(r"[^\d\-+\.]", "", str(value))
                if clean:
                    return float(clean), None
            except Exception as e:
                return None, f"Failed to coerce '{value}' to float: {e}"
            return None, f"Cannot convert '{value}' to number"

        if target_type in ("boolean", "bool"):
            if isinstance(value, bool):
                return value, None
            s = str(value).strip().lower()
            if s in ("true", "1", "yes", "t", "active", "enabled"):
                return True, None
            if s in ("false", "0", "no", "f", "inactive", "disabled"):
                return False, None
            return None, f"Cannot convert '{value}' to boolean"

        if target_type in ("array", "list"):
            if isinstance(value, list):
                return value, None
            # Split comma separated or newlines
            items = [item.strip() for item in re.split(r"[,;\n]", str(value)) if item.strip()]
            return items, None

        if target_type in ("object", "dict"):
            if isinstance(value, dict):
                return value, None
            return {"raw_value": str(value)}, None

        return value, None

    @classmethod
    def extract_structured_schema(
        cls,
        content: str,
        schema: TargetJsonSchema,
    ) -> SchemaExtractionResponse:
        """Extract schema fields from content and validate against target properties and required constraints."""
        now_dt = datetime.now(UTC)
        extracted: dict[str, Any] = {}
        errors: list[str] = []

        properties = schema.properties or {}
        required_fields = set(schema.required or [])

        # 1. Extraction phase across properties
        for prop_name, prop_meta in properties.items():
            prop_type = "string"
            allowed_enums: list[str] | None = None

            if isinstance(prop_meta, dict):
                prop_type = prop_meta.get("type", "string")
                allowed_enums = prop_meta.get("enum")
            elif isinstance(prop_meta, str):
                prop_type = prop_meta

            # Search heuristics in content:
            # Pattern A: "Prop_Name: Value" or "Prop_Name = Value" or "Prop Name: Value"
            readable_name = prop_name.replace("_", " ")
            pattern = re.compile(
                rf"(?:^|\n|\b)(?:{re.escape(prop_name)}|{re.escape(readable_name)})\s*[:=]\s*([^\n\r]+)",
                re.IGNORECASE,
            )
            match = pattern.search(content)

            raw_val: Any = None
            if match:
                raw_val = match.group(1).strip()
            else:
                # Pattern B: Markdown table or bullet search
                bullet_pattern = re.compile(
                    rf"[-*]\s*(?:{re.escape(prop_name)}|{re.escape(readable_name)})\s*[:=]\s*([^\n\r]+)",
                    re.IGNORECASE,
                )
                b_match = bullet_pattern.search(content)
                if b_match:
                    raw_val = b_match.group(1).strip()
                elif allowed_enums:
                    # Scan for any allowed enum mentions
                    for choice in allowed_enums:
                        if re.search(rf"\b{re.escape(str(choice))}\b", content, re.IGNORECASE):
                            raw_val = choice
                            break

            if raw_val is not None:
                # Type coercion
                coerced, err = cls._coerce_type(raw_val, prop_type)
                if err:
                    errors.append(f"Field '{prop_name}': {err}")
                else:
                    # Enum check
                    if allowed_enums:
                        matched_enum = next(
                            (c for c in allowed_enums if str(c).lower() == str(coerced).lower()),
                            None,
                        )
                        if matched_enum:
                            extracted[prop_name] = matched_enum
                        else:
                            errors.append(
                                f"Field '{prop_name}': Value '{coerced}' is not in allowed enums {allowed_enums}"
                            )
                    else:
                        extracted[prop_name] = coerced

        # 2. Validation phase for required fields
        for req in required_fields:
            if req not in extracted or extracted[req] is None:
                errors.append(f"Missing required property '{req}' in extracted schema")

        is_valid = len(errors) == 0

        return SchemaExtractionResponse(
            title=schema.title,
            is_valid=is_valid,
            extracted_data=extracted,
            validation_errors=errors,
            extracted_fields_count=len(extracted),
            extracted_at=now_dt,
        )
