"""Extract the text layer of a digital PDF using PyMuPDF (fitz)."""
from pathlib import Path

import pymupdf as fitz


def extract_pages(pdf_path: str | Path) -> list[str]:
    with fitz.open(pdf_path) as doc:
        # "text" preserves reading order and line breaks; "blocks" would lose table rows.
        return [page.get_text("text") for page in doc]
