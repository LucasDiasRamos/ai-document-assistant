from __future__ import annotations

from dataclasses import dataclass
import re
from collections.abc import Iterable

from app.core.config import settings
from app.services.pdf_service import ExtractedPage


_TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)


@dataclass(frozen=True, slots=True)
class TextChunk:
    page_number: int
    chunk_index: int
    content: str


def chunk_pages(
    pages: Iterable[ExtractedPage],
    *,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[TextChunk]:
    size = chunk_size if chunk_size is not None else settings.chunk_size
    overlap = (
        chunk_overlap
        if chunk_overlap is not None
        else settings.chunk_overlap
    )
    _validate_window(size=size, overlap=overlap)

    chunks: list[TextChunk] = []
    next_chunk_index = 0

    for page in pages:
        page_chunks = _chunk_page(
            page,
            chunk_size=size,
            chunk_overlap=overlap,
            start_chunk_index=next_chunk_index,
        )
        chunks.extend(page_chunks)
        next_chunk_index += len(page_chunks)

    return chunks


def _chunk_page(
    page: ExtractedPage,
    *,
    chunk_size: int,
    chunk_overlap: int,
    start_chunk_index: int,
) -> list[TextChunk]:
    text = page.text.strip()
    if not text:
        return []

    token_matches = list(_TOKEN_PATTERN.finditer(text))
    if not token_matches:
        return []

    step = chunk_size - chunk_overlap
    chunks: list[TextChunk] = []

    for window_start in range(0, len(token_matches), step):
        window_end = min(window_start + chunk_size, len(token_matches))

        first = token_matches[window_start]
        last = token_matches[window_end - 1]
        content = text[first.start() : last.end()].strip()

        chunks.append(
            TextChunk(
                page_number=page.page_number,
                chunk_index=start_chunk_index + len(chunks),
                content=content,
            )
        )

        if window_end == len(token_matches):
            break

    return chunks


def _validate_window(*, size: int, overlap: int) -> None:
    if size <= 0:
        raise ValueError("chunk_size must be greater than zero")

    if overlap < 0:
        raise ValueError("chunk_overlap cannot be negative")

    if overlap >= size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")
