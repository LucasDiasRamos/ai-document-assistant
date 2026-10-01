from pathlib import Path

import pymupdf
import pytest

from app.services.pdf_service import (
    EncryptedPdfError,
    InvalidPdfError,
    PdfNotFoundError,
    PdfPageExtractionError,
    extract_pdf_pages,
)


def create_pdf(path: Path, pages: list[str]) -> None:
    document = pymupdf.open()

    for text in pages:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)

    document.save(path)
    document.close()


def create_encrypted_pdf(path: Path) -> None:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "secret content")
    document.save(
        path,
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner-secret",
        user_pw="user-secret",
    )
    document.close()


def test_extracts_single_page_with_one_based_page_number(
    tmp_path: Path,
) -> None:
    path = tmp_path / "single.pdf"
    create_pdf(path, ["Hello from page one"])

    pages = extract_pdf_pages(path)

    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert pages[0].text == "Hello from page one"


def test_extracts_multiple_pages_preserving_page_mapping(
    tmp_path: Path,
) -> None:
    path = tmp_path / "multi.pdf"
    create_pdf(
        path,
        [
            "First page content",
            "Second page content",
            "Third page content",
        ],
    )

    pages = extract_pdf_pages(path)

    assert [page.page_number for page in pages] == [1, 2, 3]
    assert [page.text for page in pages] == [
        "First page content",
        "Second page content",
        "Third page content",
    ]


def test_blank_page_is_preserved_with_empty_text(tmp_path: Path) -> None:
    path = tmp_path / "blank.pdf"
    create_pdf(path, ["Visible text", "", "Last page"])

    pages = extract_pdf_pages(path)

    assert len(pages) == 3
    assert pages[1].page_number == 2
    assert pages[1].text == ""


def test_missing_pdf_raises_controlled_error(tmp_path: Path) -> None:
    with pytest.raises(PdfNotFoundError, match="not found"):
        extract_pdf_pages(tmp_path / "missing.pdf")


def test_corrupt_pdf_raises_controlled_error(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"%PDF-this-is-not-a-valid-document")

    with pytest.raises(InvalidPdfError, match="corrupted"):
        extract_pdf_pages(path)


def test_non_pdf_content_is_rejected_even_with_pdf_extension(
    tmp_path: Path,
) -> None:
    path = tmp_path / "fake.pdf"
    path.write_text("plain text pretending to be a PDF", encoding="utf-8")

    with pytest.raises(InvalidPdfError):
        extract_pdf_pages(path)


def test_password_protected_pdf_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "encrypted.pdf"
    create_encrypted_pdf(path)

    with pytest.raises(
        EncryptedPdfError,
        match="Password-protected PDFs are not supported",
    ):
        extract_pdf_pages(path)


def test_page_loading_failure_is_wrapped_as_page_extraction_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "partial.pdf"
    path.write_bytes(b"%PDF-placeholder")

    class FakePage:
        def get_text(self, mode: str, *, sort: bool) -> str:
            return "first page"

    class FakeDocument:
        is_pdf = True
        needs_pass = False
        page_count = 2

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def load_page(self, page_number: int):
            if page_number == 1:
                raise RuntimeError("damaged page tree")
            return FakePage()

    monkeypatch.setattr(
        "app.services.pdf_service.pymupdf.open",
        lambda _: FakeDocument(),
    )

    with pytest.raises(PdfPageExtractionError) as exc_info:
        extract_pdf_pages(path)

    assert exc_info.value.page_number == 2
    assert "page 2" in str(exc_info.value)
