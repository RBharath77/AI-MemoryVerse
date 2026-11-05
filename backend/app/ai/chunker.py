import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DocumentChunkData:
    chunk_index: int
    content: str
    token_count: int
    start_char: int
    end_char: int
    section_title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class DocumentChunker:
    """Document chunking engine supporting fixed-size, paragraph, and markdown strategies."""

    @staticmethod
    def chunk_fixed_size(
        text: str,
        chunk_size: int = 500,  # approximate words
        chunk_overlap: int = 50,  # approximate words
    ) -> list[DocumentChunkData]:
        if not text or not text.strip():
            return []

        words = text.split()
        if not words:
            return []

        chunks: list[DocumentChunkData] = []
        stride = max(1, chunk_size - chunk_overlap)
        chunk_idx = 0
        current_pos = 0

        for i in range(0, len(words), stride):
            chunk_words = words[i : i + chunk_size]
            chunk_text = " ".join(chunk_words)

            start_char = text.find(chunk_words[0], current_pos)
            if start_char == -1:
                start_char = current_pos
            end_char = start_char + len(chunk_text)
            current_pos = start_char

            token_count = int(len(chunk_words) * 1.3)
            chunks.append(
                DocumentChunkData(
                    chunk_index=chunk_idx,
                    content=chunk_text,
                    token_count=token_count,
                    start_char=start_char,
                    end_char=end_char,
                    metadata={"strategy": "fixed_size"},
                )
            )
            chunk_idx += 1

            if i + chunk_size >= len(words):
                break

        return chunks

    @staticmethod
    def chunk_markdown_semantic(
        markdown_text: str,
        max_chunk_size: int = 600,
    ) -> list[DocumentChunkData]:
        """Split markdown by header hierarchies (#, ##, ###) while preserving section titles."""
        if not markdown_text or not markdown_text.strip():
            return []

        # Find all header lines
        header_regex = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
        matches = list(header_regex.finditer(markdown_text))

        if not matches:
            # Fall back to fixed size or paragraph
            return DocumentChunker.chunk_paragraphs(markdown_text, max_words=max_chunk_size)

        chunks: list[DocumentChunkData] = []
        chunk_idx = 0

        # Intro before first header if any
        if matches[0].start() > 0:
            intro_text = markdown_text[: matches[0].start()].strip()
            if intro_text:
                words = intro_text.split()
                chunks.append(
                    DocumentChunkData(
                        chunk_index=chunk_idx,
                        content=intro_text,
                        token_count=int(len(words) * 1.3),
                        start_char=0,
                        end_char=matches[0].start(),
                        section_title="Introduction",
                        metadata={"strategy": "markdown_semantic"},
                    )
                )
                chunk_idx += 1

        for i, match in enumerate(matches):
            section_title = match.group(2).strip()
            start_pos = match.start()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(markdown_text)

            section_body = markdown_text[start_pos:end_pos].strip()
            words = section_body.split()

            if len(words) <= max_chunk_size:
                chunks.append(
                    DocumentChunkData(
                        chunk_index=chunk_idx,
                        content=section_body,
                        token_count=int(len(words) * 1.3),
                        start_char=start_pos,
                        end_char=end_pos,
                        section_title=section_title,
                        metadata={"strategy": "markdown_semantic", "level": len(match.group(1))},
                    )
                )
                chunk_idx += 1
            else:
                # Sub-chunk large section
                sub_chunks = DocumentChunker.chunk_fixed_size(
                    section_body,
                    chunk_size=max_chunk_size,
                    chunk_overlap=50,
                )
                for sc in sub_chunks:
                    sc.chunk_index = chunk_idx
                    sc.start_char += start_pos
                    sc.end_char += start_pos
                    sc.section_title = section_title
                    sc.metadata["strategy"] = "markdown_semantic_subchunk"
                    chunks.append(sc)
                    chunk_idx += 1

        return chunks

    @staticmethod
    def chunk_paragraphs(
        text: str,
        max_words: int = 500,
    ) -> list[DocumentChunkData]:
        """Split text along paragraph breaks (double newlines)."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            return []

        chunks: list[DocumentChunkData] = []
        chunk_idx = 0
        current_block: list[str] = []
        current_words = 0
        current_start = 0

        for p in paragraphs:
            p_words = len(p.split())
            if current_words + p_words > max_words and current_block:
                joined = "\n\n".join(current_block)
                chunks.append(
                    DocumentChunkData(
                        chunk_index=chunk_idx,
                        content=joined,
                        token_count=int(current_words * 1.3),
                        start_char=current_start,
                        end_char=current_start + len(joined),
                        metadata={"strategy": "paragraphs"},
                    )
                )
                chunk_idx += 1
                current_block = [p]
                current_words = p_words
                current_start = text.find(p, current_start + len(joined))
            else:
                current_block.append(p)
                current_words += p_words

        if current_block:
            joined = "\n\n".join(current_block)
            chunks.append(
                DocumentChunkData(
                    chunk_index=chunk_idx,
                    content=joined,
                    token_count=int(current_words * 1.3),
                    start_char=current_start,
                    end_char=current_start + len(joined),
                    metadata={"strategy": "paragraphs"},
                )
            )

        return chunks

    @classmethod
    def auto_chunk(
        cls,
        text: str,
        filename: str = "",
        mime_type: str = "",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> list[DocumentChunkData]:
        """Automatically select the optimal chunking strategy based on file format."""
        ext = filename.lower().split(".")[-1] if "." in filename else ""

        if ext in ("md", "markdown") or "markdown" in mime_type:
            return cls.chunk_markdown_semantic(text, max_chunk_size=chunk_size)

        if "\n\n" in text:
            return cls.chunk_paragraphs(text, max_words=chunk_size)

        return cls.chunk_fixed_size(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
