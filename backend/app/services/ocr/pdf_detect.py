"""Decide whether a PDF has a real text layer ("digital") or is a scan.

Flowchart node: "Is PDF Digital?"
"""
from pathlib import Path

import pymupdf as fitz

from app.config import get_settings


def page_text_lengths(pdf_path: str | Path) -> list[int]:
    """Number of non-whitespace characters extractable from each page."""
    with fitz.open(pdf_path) as doc:
        return [len("".join(page.get_text("text").split())) for page in doc]


def is_digital_pdf(pdf_path: str | Path, min_chars_per_page: int | None = None) -> bool:
    """A PDF is 'digital' when at least half its pages carry a usable text layer.

    Scanned documents often contain a page or two of digital cover text, so the
    threshold is on the majority of pages rather than any single page.
    """
    threshold = min_chars_per_page or get_settings().min_chars_per_page_for_digital
    lengths = page_text_lengths(pdf_path)
    if not lengths:
        return False
    digital_pages = sum(1 for n in lengths if n >= threshold)
    return digital_pages * 2 >= len(lengths)
