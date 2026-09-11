"""Digital-vs-scanned classification for the OCR branch decision."""
import pymupdf as fitz
import pytest

from app.services.ocr.pdf_detect import is_digital_pdf, page_text_lengths


@pytest.fixture
def digital_pdf(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Complete Blood Count\nHemoglobin 13.5 g/dL\nWBC 7.2 x10^3/uL", fontsize=12)
    path = tmp_path / "digital.pdf"
    doc.save(path)
    return path


@pytest.fixture
def scanned_pdf(tmp_path):
    """A PDF whose only content is an image (no text layer) - what a scanner produces."""
    doc = fitz.open()
    page = doc.new_page()
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 200, 100), False)
    pix.clear_with(255)
    page.insert_image(page.rect, pixmap=pix)
    path = tmp_path / "scanned.pdf"
    doc.save(path)
    return path


def test_digital_pdf_is_detected(digital_pdf):
    assert is_digital_pdf(digital_pdf) is True


def test_image_only_pdf_is_treated_as_scanned(scanned_pdf):
    assert is_digital_pdf(scanned_pdf) is False


def test_page_text_lengths_reports_each_page(digital_pdf):
    lengths = page_text_lengths(digital_pdf)
    assert len(lengths) == 1
    assert lengths[0] > 40
