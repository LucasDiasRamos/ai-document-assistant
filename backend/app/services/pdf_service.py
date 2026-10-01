from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pymupdf


class PdfExtractionError(RuntimeError):
    """Base error for PDF text extraction failures."""


class PdfNotFoundError(PdfExtractionError):
    pass


class InvalidPdfError(PdfExtractionError):
    pass


class EncryptedPdfError(PdfExtractionError):
    pass


class PdfPageExtractionError(PdfExtractionError):
    def __init__(self, page_number: int) -> None:
        super().__init__(f"Failed to extract text from PDF page {page_number}")
        self.page_number = page_number


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    page_number: int
    text: str


def extract_pdf_pages(path: str | Path) -> list[ExtractedPage]:
    pdf_path = Path(path).expanduser().resolve()

    if not pdf_path.is_file():
        raise PdfNotFoundError(f"PDF file was not found: {pdf_path}")

    try:
        document = pymupdf.open(pdf_path)
    except (RuntimeError, ValueError) as exc:
        raise InvalidPdfError("PDF could not be opened or is corrupted") from exc

    with document:
        if not document.is_pdf:
            raise InvalidPdfError("Stored file is not a PDF")

        if document.needs_pass:
            raise EncryptedPdfError(
                "Password-protected PDFs are not supported"
            )

        pages: list[ExtractedPage] = []

        for page_index, page in enumerate(document, start=1):
            try:
                raw_text = page.get_text("text", sort=True)
            except RuntimeError as exc:
                raise PdfPageExtractionError(page_index) from exc

            pages.append(
                ExtractedPage(
                    page_number=page_index,
                    text=_normalize_text(raw_text),
                )
            )

        return pages


def _normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in normalized.split("\n")]

    while lines and not lines[0]:
        lines.pop(0)

    while lines and not lines[-1]:
        lines.pop()

    return "\n".join(lines)
