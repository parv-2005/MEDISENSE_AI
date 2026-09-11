"""Scanned PDF / image branch: render -> preprocess -> Tesseract."""
from pathlib import Path

import pymupdf as fitz
import pytesseract
from PIL import Image

from app.config import get_settings
from app.services.ocr.preprocess import preprocess_for_ocr

TESSERACT_INSTALL_HINT = (
    "Tesseract OCR binary was not found. Install it (Windows: https://github.com/UB-Mannheim/tesseract/wiki, "
    "macOS: `brew install tesseract`, Debian/Ubuntu: `sudo apt install tesseract-ocr`) and either add it to "
    "PATH or set TESSERACT_CMD in backend/.env."
)


def _configure_tesseract() -> None:
    cmd = get_settings().tesseract_cmd
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd


def render_pdf_pages(pdf_path: str | Path, dpi: int | None = None) -> list[Image.Image]:
    """Rasterise each PDF page with PyMuPDF (no Poppler dependency needed)."""
    dpi = dpi or get_settings().ocr_dpi
    images: list[Image.Image] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
            images.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
    return images


def ocr_image(image: Image.Image) -> str:
    """Run Tesseract on a single (already preprocessed) image."""
    _configure_tesseract()
    try:
        # psm 6 = assume a uniform block of text; works well for tabular lab reports.
        return pytesseract.image_to_string(image, lang="eng", config="--oem 3 --psm 6")
    except pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError(TESSERACT_INSTALL_HINT) from exc


def ocr_images(images: list[Image.Image]) -> list[str]:
    return [ocr_image(preprocess_for_ocr(im)) for im in images]
