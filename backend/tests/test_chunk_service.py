import pytest

from app.services.chunk_service import chunk_pages
from app.services.pdf_service import ExtractedPage


def test_short_page_produces_one_chunk() -> None:
    pages = [
        ExtractedPage(
            page_number=1,
            text="A short page with useful content.",
        )
    ]

    chunks = chunk_pages(
        pages,
        chunk_size=20,
        chunk_overlap=4,
    )

    assert len(chunks) == 1
    assert chunks[0].page_number == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].content == "A short page with useful content."


def test_long_page_produces_overlapping_chunks() -> None:
    pages = [
        ExtractedPage(
            page_number=1,
            text="one two three four five six",
        )
    ]

    chunks = chunk_pages(
        pages,
        chunk_size=4,
        chunk_overlap=2,
    )

    assert [chunk.content for chunk in chunks] == [
        "one two three four",
        "three four five six",
    ]
    assert [chunk.chunk_index for chunk in chunks] == [0, 1]


def test_chunks_never_cross_page_boundaries() -> None:
    pages = [
        ExtractedPage(page_number=1, text="alpha beta gamma delta"),
        ExtractedPage(page_number=2, text="epsilon zeta eta theta"),
    ]

    chunks = chunk_pages(
        pages,
        chunk_size=3,
        chunk_overlap=1,
    )

    assert [(chunk.page_number, chunk.content) for chunk in chunks] == [
        (1, "alpha beta gamma"),
        (1, "gamma delta"),
        (2, "epsilon zeta eta"),
        (2, "eta theta"),
    ]


def test_chunk_indexes_are_global_and_deterministic() -> None:
    pages = [
        ExtractedPage(page_number=4, text="one two three four"),
        ExtractedPage(page_number=8, text="five six seven eight"),
    ]

    first_run = chunk_pages(
        pages,
        chunk_size=3,
        chunk_overlap=1,
    )
    second_run = chunk_pages(
        pages,
        chunk_size=3,
        chunk_overlap=1,
    )

    assert [chunk.chunk_index for chunk in first_run] == [0, 1, 2, 3]
    assert first_run == second_run
    assert [chunk.page_number for chunk in first_run] == [4, 4, 8, 8]


def test_blank_pages_are_skipped_without_breaking_indexes() -> None:
    pages = [
        ExtractedPage(page_number=1, text="first content"),
        ExtractedPage(page_number=2, text="   \n\n"),
        ExtractedPage(page_number=3, text="last content"),
    ]

    chunks = chunk_pages(
        pages,
        chunk_size=10,
        chunk_overlap=2,
    )

    assert [(chunk.page_number, chunk.chunk_index) for chunk in chunks] == [
        (1, 0),
        (3, 1),
    ]


def test_punctuation_counts_as_lexical_units_and_text_is_preserved() -> None:
    pages = [
        ExtractedPage(
            page_number=1,
            text="Hello, world! Next sentence.",
        )
    ]

    chunks = chunk_pages(
        pages,
        chunk_size=4,
        chunk_overlap=1,
    )

    assert chunks[0].content == "Hello, world!"


@pytest.mark.parametrize(
    ("chunk_size", "chunk_overlap", "message"),
    [
        (0, 0, "greater than zero"),
        (10, -1, "cannot be negative"),
        (10, 10, "smaller than chunk_size"),
        (10, 11, "smaller than chunk_size"),
    ],
)
def test_invalid_chunk_window_is_rejected(
    chunk_size: int,
    chunk_overlap: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        chunk_pages(
            [ExtractedPage(page_number=1, text="content")],
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )


def test_empty_page_list_returns_no_chunks() -> None:
    assert chunk_pages([], chunk_size=10, chunk_overlap=2) == []
