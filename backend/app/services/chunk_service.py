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


@dataclass(frozen=True, slots=True)
class _TextSpan:
    start: int
    end: int


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

    token_spans = _build_token_spans(text, chunk_size=chunk_size)
    if not token_spans:
        return []

    step = chunk_size - chunk_overlap
    chunks: list[TextChunk] = []

    for window_start in range(0, len(token_spans), step):
        window_end = min(window_start + chunk_size, len(token_spans))

        first = token_spans[window_start]
        last = token_spans[window_end - 1]
        content = text[first.start : last.end].strip()

        chunks.append(
            TextChunk(
                page_number=page.page_number,
                chunk_index=start_chunk_index + len(chunks),
                content=content,
            )
        )

        if window_end == len(token_spans):
            break

    return chunks


def _build_token_spans(text: str, *, chunk_size: int) -> list[_TextSpan]:
    spans: list[_TextSpan] = []

    for match in _TOKEN_PATTERN.finditer(text):
        token = match.group(0)

        if _needs_character_fallback(token, chunk_size=chunk_size):
            spans.extend(
                _TextSpan(index, index + 1)
                for index in range(match.start(), match.end())
            )
            continue

        spans.append(_TextSpan(match.start(), match.end()))

    return spans


def _needs_character_fallback(token: str, *, chunk_size: int) -> bool:
    if len(token) > chunk_size:
        return True

    return any(_is_cjk_character(character) for character in token)


def _is_cjk_character(character: str) -> bool:
    codepoint = ord(character)

    return (
        0x3040 <= codepoint <= 0x30FF  # Hiragana and Katakana
        or 0x3400 <= codepoint <= 0x4DBF  # CJK Extension A
        or 0x4E00 <= codepoint <= 0x9FFF  # CJK Unified Ideographs
        or 0xAC00 <= codepoint <= 0xD7AF  # Hangul syllables
        or 0xF900 <= codepoint <= 0xFAFF  # CJK Compatibility Ideographs
    )


def _validate_window(*, size: int, overlap: int) -> None:
    if size <= 0:
        raise ValueError("chunk_size must be greater than zero")

    if overlap < 0:
        raise ValueError("chunk_overlap cannot be negative")

    if overlap >= size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")
