from __future__ import annotations

import csv
import io
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("memoryverse.table_extractor")


@dataclass
class TabularChunkData:
    chunk_index: int
    content: str
    token_count: int
    table_id: str
    row_range: tuple[int, int]
    columns: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedTableResult:
    table_id: str
    columns: list[str]
    rows: list[list[str]]
    structured_records: list[dict[str, str]]
    chunks: list[TabularChunkData]
    row_count: int
    caption: str | None = None


class StructuredTableExtractor:
    """Enterprise multi-modal table extraction & header-preserving tabular chunker."""

    MARKDOWN_TABLE_REGEX = re.compile(
        r"((?:^[ \t]*\|[^\n]+\|[ \t]*\n)"  # Header row
        r"(?:^[ \t]*\|[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)+\|[ \t]*\n)"  # Separator row
        r"(?:^[ \t]*\|[^\n]+\|[ \t]*\n?)+)",  # 1+ Data rows
        re.MULTILINE,
    )

    @classmethod
    def _parse_markdown_cells(cls, line: str) -> list[str]:
        """Split a Markdown table row into clean stripped cells."""
        raw = line.strip()
        if raw.startswith("|"):
            raw = raw[1:]
        if raw.endswith("|"):
            raw = raw[:-1]
        return [cell.strip() for cell in raw.split("|")]

    @classmethod
    def parse_markdown_tables(
        cls,
        text: str,
        rows_per_chunk: int = 10,
    ) -> list[ExtractedTableResult]:
        """Extract markdown tables, convert to structured records, and generate header-preserving chunks."""
        results: list[ExtractedTableResult] = []

        for match in cls.MARKDOWN_TABLE_REGEX.finditer(text):
            table_str = match.group(1).strip()
            lines = [line_str.strip() for line_str in table_str.split("\n") if line_str.strip()]
            if len(lines) < 3:
                continue

            header_cells = cls._parse_markdown_cells(lines[0])
            columns = [c if c else f"col_{idx + 1}" for idx, c in enumerate(header_cells)]
            separator_line = lines[1]
            data_lines = lines[2:]

            rows: list[list[str]] = []
            records: list[dict[str, str]] = []

            for line in data_lines:
                cells = cls._parse_markdown_cells(line)
                # Pad or truncate cells to match column count
                if len(cells) < len(columns):
                    cells.extend([""] * (len(columns) - len(cells)))
                else:
                    cells = cells[: len(columns)]

                rows.append(cells)
                rec = {columns[i]: cells[i] for i in range(len(columns))}
                records.append(rec)

            table_id = f"tbl_{uuid.uuid4().hex[:10]}"
            chunks: list[TabularChunkData] = []
            chunk_idx = 0

            # Generate header-preserving slices
            for r_start in range(0, len(rows), rows_per_chunk):
                r_end = min(r_start + rows_per_chunk, len(rows))
                slice_rows = rows[r_start:r_end]

                chunk_lines = [
                    "| " + " | ".join(columns) + " |",
                    separator_line,
                ]
                for row_cells in slice_rows:
                    chunk_lines.append("| " + " | ".join(row_cells) + " |")

                chunk_content = "\n".join(chunk_lines)
                token_count = int(len(chunk_content.split()) * 1.3)

                chunks.append(
                    TabularChunkData(
                        chunk_index=chunk_idx,
                        content=chunk_content,
                        token_count=token_count,
                        table_id=table_id,
                        row_range=(r_start + 1, r_end),
                        columns=columns,
                        metadata={
                            "strategy": "header_preserving_tabular",
                            "total_rows": len(rows),
                            "table_id": table_id,
                            "columns": columns,
                        },
                    )
                )
                chunk_idx += 1

            results.append(
                ExtractedTableResult(
                    table_id=table_id,
                    columns=columns,
                    rows=rows,
                    structured_records=records,
                    chunks=chunks,
                    row_count=len(rows),
                )
            )

        return results

    @classmethod
    def parse_csv_table(
        cls,
        csv_text: str,
        rows_per_chunk: int = 10,
    ) -> ExtractedTableResult | None:
        """Parse raw CSV or TSV string into structured table and header-preserving markdown chunks."""
        try:
            reader = csv.reader(io.StringIO(csv_text.strip()))
            rows_list = list(reader)
            if len(rows_list) < 2:
                return None

            header = [h.strip() for h in rows_list[0]]
            columns = [c if c else f"col_{idx + 1}" for idx, c in enumerate(header)]
            data_rows = rows_list[1:]

            records: list[dict[str, str]] = []
            normalized_rows: list[list[str]] = []

            for row in data_rows:
                cells = [c.strip() for c in row]
                if len(cells) < len(columns):
                    cells.extend([""] * (len(columns) - len(cells)))
                else:
                    cells = cells[: len(columns)]
                normalized_rows.append(cells)
                records.append({columns[i]: cells[i] for i in range(len(columns))})

            table_id = f"tbl_csv_{uuid.uuid4().hex[:10]}"
            separator = "| " + " | ".join(["---"] * len(columns)) + " |"
            header_str = "| " + " | ".join(columns) + " |"
            chunks: list[TabularChunkData] = []
            chunk_idx = 0

            for r_start in range(0, len(normalized_rows), rows_per_chunk):
                r_end = min(r_start + rows_per_chunk, len(normalized_rows))
                slice_rows = normalized_rows[r_start:r_end]

                chunk_lines = [header_str, separator]
                for r in slice_rows:
                    chunk_lines.append("| " + " | ".join(r) + " |")

                chunk_content = "\n".join(chunk_lines)
                chunks.append(
                    TabularChunkData(
                        chunk_index=chunk_idx,
                        content=chunk_content,
                        token_count=int(len(chunk_content.split()) * 1.3),
                        table_id=table_id,
                        row_range=(r_start + 1, r_end),
                        columns=columns,
                        metadata={
                            "strategy": "header_preserving_tabular",
                            "source_format": "csv",
                            "total_rows": len(normalized_rows),
                        },
                    )
                )
                chunk_idx += 1

            return ExtractedTableResult(
                table_id=table_id,
                columns=columns,
                rows=normalized_rows,
                structured_records=records,
                chunks=chunks,
                row_count=len(normalized_rows),
            )
        except Exception as e:
            logger.warning("Failed to parse CSV table: %s", e)
            return None

    @classmethod
    def extract_all_tables(
        cls,
        text: str,
        rows_per_chunk: int = 10,
    ) -> list[ExtractedTableResult]:
        """Extract markdown and raw CSV tabular structures from document content."""
        tables = cls.parse_markdown_tables(text, rows_per_chunk=rows_per_chunk)
        if not tables and ("," in text or "\t" in text):
            # Attempt CSV parsing if no markdown tables found
            csv_table = cls.parse_csv_table(text, rows_per_chunk=rows_per_chunk)
            if csv_table:
                tables.append(csv_table)
        return tables

    @classmethod
    def extract_markdown_tables(
        cls,
        text: str,
        rows_per_chunk: int = 10,
    ) -> list[ExtractedTableResult]:
        """Convenience alias for parse_markdown_tables."""
        return cls.parse_markdown_tables(text, rows_per_chunk=rows_per_chunk)

    @classmethod
    def extract_csv_tables(
        cls,
        text: str,
        rows_per_chunk: int = 10,
    ) -> list[ExtractedTableResult]:
        """Extract CSV table and return as list of ExtractedTableResult."""
        t = cls.parse_csv_table(text, rows_per_chunk=rows_per_chunk)
        return [t] if t else []
