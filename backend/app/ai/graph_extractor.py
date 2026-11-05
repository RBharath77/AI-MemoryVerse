import json
import logging
import re
from dataclasses import dataclass, field

from app.ai.factory import get_llm_provider
from app.models.graph import EntityType

logger = logging.getLogger(__name__)


@dataclass
class ExtractedEntity:
    name: str
    entity_type: EntityType
    description: str | None = None
    aliases: list[str] = field(default_factory=list)


@dataclass
class ExtractedRelationship:
    source_name: str
    target_name: str
    relationship_type: str
    confidence: float = 1.0


@dataclass
class GraphExtractionResult:
    entities: list[ExtractedEntity]
    relationships: list[ExtractedRelationship]


class GraphExtractor:
    """Extracts entities and relationships from unstructured knowledge text."""

    KNOWN_TECH = {
        "python": "Python programming language",
        "typescript": "TypeScript programming language",
        "javascript": "JavaScript language",
        "react": "React frontend library",
        "next.js": "Next.js full-stack React framework",
        "fastapi": "FastAPI async web framework",
        "postgresql": "PostgreSQL relational database",
        "pgvector": "pgvector vector similarity extension",
        "docker": "Docker container runtime",
        "redis": "Redis in-memory data store",
        "celery": "Celery asynchronous task queue",
        "render": "Render cloud deployment platform",
        "tailwind": "Tailwind CSS styling framework",
        "sqlite": "SQLite embedded relational database",
        "aws": "Amazon Web Services cloud platform",
        "github": "GitHub code hosting platform",
        "jwt": "JSON Web Token auth standard",
        "argon2": "Argon2id password hashing function",
    }

    RELATION_PATTERNS = [
        (
            r"(\b[A-Za-z0-9_-]+\b)\s+(?:uses|utilizes|built with|powered by)\s+"
            r"(\b[A-Za-z0-9_-]+\b)",
            "uses_technology",
        ),
        (
            r"(\b[A-Za-z0-9_-]+\b)\s+(?:deployed on|hosted on|running on)\s+(\b[A-Za-z0-9_-]+\b)",
            "deployed_on",
        ),
        (
            r"(\b[A-Za-z0-9_-]+\b)\s+(?:works with|collaborates with|met with)\s+"
            r"(\b[A-Za-z0-9_-]+\b)",
            "collaborates_with",
        ),
        (
            r"(\b[A-Za-z0-9_-]+\b)\s+(?:lives in|moved to|relocated to|located in)\s+"
            r"(\b[A-Za-z0-9_-]+\b)",
            "located_in",
        ),
        (
            r"(\b[A-Za-z0-9_-]+\b)\s+(?:depends on|requires|integrates with)\s+"
            r"(\b[A-Za-z0-9_-]+\b)",
            "depends_on",
        ),
        (
            r"(\b[A-Za-z0-9_-]+\b)\s+(?:maintains|leads|created|authored)\s+(\b[A-Za-z0-9_-]+\b)",
            "maintains",
        ),
    ]

    @classmethod
    async def extract(cls, text: str) -> GraphExtractionResult:
        if not text or not text.strip():
            return GraphExtractionResult(entities=[], relationships=[])

        # 1. Attempt LLM structured extraction if configured
        try:
            llm = get_llm_provider()
            prompt = (
                "You are an Entity and Knowledge Graph Extractor. "
                "Extract entities and relationships from the text.\n"
                "Return JSON with 'entities': list of {'name': str, "
                "'type': 'person'|'organization'|'technology'|'project'|'concept',\n"
                "'description': str},\n"
                "and 'relationships': list of {'source': str, 'target': str, 'type': str}.\n\n"
                f"Input text:\n{text}"
            )
            resp = await llm.generate_text(
                prompt=prompt,
                system_prompt="You extract clean knowledge graph triplets strictly in JSON format.",
            )
            raw = resp.content.strip()
            # If wrapped in markdown code fence, strip it
            if "```" in raw:
                raw = re.sub(r"^```(?:json)?\n", "", raw)
                raw = re.sub(r"\n```$", "", raw)

            parsed = json.loads(raw)
            entities = []
            for e in parsed.get("entities", []):
                t_str = e.get("type", "concept").lower()
                try:
                    e_type = EntityType(t_str)
                except ValueError:
                    e_type = EntityType.CONCEPT
                entities.append(
                    ExtractedEntity(
                        name=e["name"].strip(),
                        entity_type=e_type,
                        description=e.get("description"),
                    )
                )

            relationships = []
            for r in parsed.get("relationships", []):
                relationships.append(
                    ExtractedRelationship(
                        source_name=r["source"].strip(),
                        target_name=r["target"].strip(),
                        relationship_type=r["type"].strip().lower().replace(" ", "_"),
                    )
                )

            if entities or relationships:
                return GraphExtractionResult(entities=entities, relationships=relationships)
        except Exception:
            # Fall back to high-precision rule-based extraction
            pass

        return cls._rule_based_extract(text)

    @classmethod
    def _rule_based_extract(cls, text: str) -> GraphExtractionResult:
        entities_dict: dict[str, ExtractedEntity] = {}
        relationships: list[ExtractedRelationship] = []

        lower_text = text.lower()

        # 1. Detect known technologies
        for tech, desc in cls.KNOWN_TECH.items():
            if re.search(rf"\b{re.escape(tech)}\b", lower_text):
                # Capitalize appropriately
                if tech not in ("postgresql", "pgvector", "next.js", "jwt"):
                    display_name = tech.capitalize()
                else:
                    display_name = tech
                if tech == "postgresql":
                    display_name = "PostgreSQL"
                elif tech == "pgvector":
                    display_name = "pgvector"
                elif tech == "next.js":
                    display_name = "Next.js"
                elif tech == "jwt":
                    display_name = "JWT"

                entities_dict[display_name.lower()] = ExtractedEntity(
                    name=display_name,
                    entity_type=EntityType.TECHNOLOGY,
                    description=desc,
                )

        # 2. Detect Projects (e.g. "Project Apollo", "Project Orion", "AI-MemoryVerse")
        proj_matches = re.finditer(
            r"\b(?:Project\s+([A-Za-z0-9_-]+)|(AI-MemoryVerse))\b",
            text,
            re.IGNORECASE,
        )
        for pm in proj_matches:
            p_name = pm.group(1) or pm.group(2)
            display = f"Project {p_name.capitalize()}" if not p_name.startswith("AI") else p_name
            entities_dict[display.lower()] = ExtractedEntity(
                name=display,
                entity_type=EntityType.PROJECT,
                description=f"{display} initiative",
            )

        # 3. Detect People (e.g. "Met with Jane", "Jane Doe works with Bob")
        person_matches = re.finditer(
            r"\b(?:met with|talked to|collaborated with|assigned to)\s+"
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b",
            text,
        )
        for per in person_matches:
            name = per.group(1).strip()
            entities_dict[name.lower()] = ExtractedEntity(
                name=name,
                entity_type=EntityType.PERSON,
            )

        # 4. Extract relationships via patterns
        for pattern, rel_type in cls.RELATION_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                src = match.group(1).strip()
                tgt = match.group(2).strip()

                # Find closest entity keys
                src_key = next(
                    (k for k in entities_dict if k in src.lower() or src.lower() in k),
                    None,
                )
                tgt_key = next(
                    (k for k in entities_dict if k in tgt.lower() or tgt.lower() in k),
                    None,
                )

                if src_key and tgt_key and src_key != tgt_key:
                    relationships.append(
                        ExtractedRelationship(
                            source_name=entities_dict[src_key].name,
                            target_name=entities_dict[tgt_key].name,
                            relationship_type=rel_type,
                        )
                    )

        # If entities found without explicit pattern relationships, link project to technologies
        tech_entities = [
            e for e in entities_dict.values() if e.entity_type == EntityType.TECHNOLOGY
        ]
        proj_entities = [
            e for e in entities_dict.values() if e.entity_type == EntityType.PROJECT
        ]
        if proj_entities and tech_entities and not relationships:
            p = proj_entities[0]
            for t in tech_entities[:4]:
                relationships.append(
                    ExtractedRelationship(
                        source_name=p.name,
                        target_name=t.name,
                        relationship_type="uses_technology",
                    )
                )

        return GraphExtractionResult(
            entities=list(entities_dict.values()),
            relationships=relationships,
        )
