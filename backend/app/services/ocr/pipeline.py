"""Text Extraction (OCR Pipeline) orchestrator - flowchart stage 3."""
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from app.services.ocr import digital, scanned
from app.services.ocr.cleaner import clean_text
from app.services.ocr.pdf_detect import is_digital_pdf

PDF_TYPES = {"application/pdf"}
IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/tiff", "image/bmp"}
SUPPORTED_TYPES = PDF_TYPES | IMAGE_TYPES


@dataclass
class ExtractionResult:
    text: str
    method: str  # "digital" | "ocr"
    page_count: int
    pages: list[str]


def extract_text_from_file(path: str | Path, content_type: str) -> ExtractionResult:
    path = Path(path)
    content_type = (content_type or "").lower()

    if content_type in PDF_TYPES:
        if is_digital_pdf(path):
            raw_pages = digital.extract_pages(path)
            method = "digital"
        else:
            raw_pages = scanned.ocr_images(scanned.render_pdf_pages(path))
            method = "ocr"
    elif content_type in IMAGE_TYPES:
        with Image.open(path) as im:
            raw_pages = scanned.ocr_images([im.convert("RGB")])
        method = "ocr"
    else:
        raise ValueError(f"Unsupported file type '{content_type}'. Upload a PDF or an image.")

    cleaned_pages = [clean_text(p) for p in raw_pages]
    text = "\n\n".join(p for p in cleaned_pages if p)
    return ExtractionResult(text=text, method=method, page_count=len(raw_pages), pages=cleaned_pages)
