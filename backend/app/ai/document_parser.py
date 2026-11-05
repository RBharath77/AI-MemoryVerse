import csv
import io
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ParsedDocument:
    text: str
    page_count: int = 1
    word_count: int = 0
    token_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    summary: str = ""


class DocumentParser:
    """Parses various document types into clean extracted text and structured metadata."""

    @classmethod
    def parse(cls, file_bytes: bytes, filename: str, mime_type: str = "") -> ParsedDocument:
        ext = filename.lower().split(".")[-1] if "." in filename else ""

        try:
            if ext == "pdf" or "pdf" in mime_type:
                return cls._parse_pdf(file_bytes)
            elif ext in ("docx", "doc") or "word" in mime_type or "officedocument" in mime_type:
                return cls._parse_docx(file_bytes)
            elif ext == "csv" or "csv" in mime_type:
                return cls._parse_csv(file_bytes)
            elif ext == "json" or "json" in mime_type:
                return cls._parse_json(file_bytes)
            elif ext in ("html", "htm") or "html" in mime_type:
                return cls._parse_html(file_bytes)
            else:
                # Default to text / markdown
                return cls._parse_text(file_bytes)
        except Exception as e:
            logger.error(f"Error parsing document '{filename}': {e}", exc_info=True)
            # Fallback to UTF-8 decoding
            return cls._parse_text(file_bytes)

    @classmethod
    def _parse_pdf(cls, file_bytes: bytes) -> ParsedDocument:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(file_bytes))
        pages_text = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                pages_text.append(t.strip())

        full_text = "\n\n".join(pages_text)
        page_count = max(1, len(reader.pages))
        words = full_text.split()

        pdf_meta = {}
        if reader.metadata:
            for k, v in reader.metadata.items():
                if v and isinstance(v, (str, int, float)):
                    clean_k = k.lstrip("/").lower()
                    pdf_meta[clean_k] = str(v)

        return ParsedDocument(
            text=full_text,
            page_count=page_count,
            word_count=len(words),
            token_count=int(len(words) * 1.3),
            metadata=pdf_meta,
            summary=full_text[:300].strip(),
        )

    @classmethod
    def _parse_docx(cls, file_bytes: bytes) -> ParsedDocument:
        from docx import Document as DocxDocument

        doc = DocxDocument(io.BytesIO(file_bytes))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        full_text = "\n\n".join(paragraphs)
        words = full_text.split()

        return ParsedDocument(
            text=full_text,
            page_count=max(1, len(paragraphs) // 5),
            word_count=len(words),
            token_count=int(len(words) * 1.3),
            summary=full_text[:300].strip(),
        )

    @classmethod
    def _parse_csv(cls, file_bytes: bytes) -> ParsedDocument:
        raw = file_bytes.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(raw))
        rows = [" | ".join(r) for r in reader if r]
        full_text = "\n".join(rows)
        words = full_text.split()

        return ParsedDocument(
            text=full_text,
            page_count=max(1, len(rows) // 40),
            word_count=len(words),
            token_count=int(len(words) * 1.3),
            summary=f"CSV table with {len(rows)} rows.",
        )

    @classmethod
    def _parse_json(cls, file_bytes: bytes) -> ParsedDocument:
        raw = file_bytes.decode("utf-8", errors="replace")
        try:
            data = json.loads(raw)
            full_text = json.dumps(data, indent=2)
        except Exception:
            full_text = raw
        words = full_text.split()

        return ParsedDocument(
            text=full_text,
            page_count=1,
            word_count=len(words),
            token_count=int(len(words) * 1.3),
            summary=full_text[:300].strip(),
        )

    @classmethod
    def _parse_html(cls, file_bytes: bytes) -> ParsedDocument:
        raw = file_bytes.decode("utf-8", errors="replace")
        clean = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", raw, flags=re.IGNORECASE)
        clean = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"<[^>]+>", " ", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        words = clean.split()

        return ParsedDocument(
            text=clean,
            page_count=1,
            word_count=len(words),
            token_count=int(len(words) * 1.3),
            summary=clean[:300].strip(),
        )

    @classmethod
    def _parse_text(cls, file_bytes: bytes) -> ParsedDocument:
        raw = file_bytes.decode("utf-8", errors="replace")
        words = raw.split()
        return ParsedDocument(
            text=raw,
            page_count=max(1, len(raw.splitlines()) // 40),
            word_count=len(words),
            token_count=int(len(words) * 1.3),
            summary=raw[:300].strip(),
        )
