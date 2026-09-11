import pymupdf as fitz
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.services.ocr import digital, scanned
from app.services.ocr.pipeline import ExtractionResult, extract_text_from_file


@pytest.fixture
def digital_pdf(tmp_path):
    doc = fitz.open()
    p1 = doc.new_page(); p1.insert_text((72, 72), "Page one: Complete Blood Count report. Hemoglobin 13.5 g/dL (ref 12-16). Hematocrit 41%.", fontsize=12)
    p2 = doc.new_page(); p2.insert_text((72, 72), "Page two: WBC 7.2 x10^3/uL (ref 4-11). Platelets 250 x10^3/uL (ref 150-400).", fontsize=12)
    path = tmp_path / "d.pdf"; doc.save(path)
    return path


def test_digital_extractor_returns_text_per_page(digital_pdf):
    pages = digital.extract_pages(digital_pdf)
    assert len(pages) == 2
    assert "Hemoglobin 13.5" in pages[0]
    assert "WBC 7.2" in pages[1]


def test_pdf_pages_render_to_images(digital_pdf):
    images = scanned.render_pdf_pages(digital_pdf, dpi=72)
    assert len(images) == 2
    assert all(isinstance(im, Image.Image) for im in images)


def test_pipeline_uses_digital_branch_for_text_pdfs(digital_pdf):
    result = extract_text_from_file(digital_pdf, "application/pdf")
    assert isinstance(result, ExtractionResult)
    assert result.method == "digital"
    assert result.page_count == 2
    assert "Hemoglobin 13.5 g/dL" in result.text
    assert "WBC 7.2" in result.text


def test_pipeline_routes_images_to_ocr_branch(tmp_path, monkeypatch):
    img = Image.new("RGB", (400, 100), "white")
    ImageDraw.Draw(img).text((10, 40), "Glucose 105 mg/dL", fill="black", font=ImageFont.load_default())
    path = tmp_path / "scan.png"; img.save(path)

    # Tesseract binary may not exist on the test machine: stub the OCR call itself,
    # everything else (routing, preprocessing, cleaning) runs for real.
    monkeypatch.setattr(scanned, "ocr_image", lambda im: "Glucose  1O5 mg/dL\n\n\n")
    result = extract_text_from_file(path, "image/png")
    assert result.method == "ocr"
    assert result.page_count == 1
    assert result.text == "Glucose 105 mg/dL"


def test_pipeline_rejects_unsupported_types(tmp_path):
    path = tmp_path / "x.docx"; path.write_bytes(b"nope")
    with pytest.raises(ValueError):
        extract_text_from_file(path, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")


def test_missing_tesseract_gives_actionable_error(tmp_path, monkeypatch):
    import pytesseract
    path = tmp_path / "scan.png"; Image.new("RGB", (50, 50), "white").save(path)

    def boom(*a, **k):
        raise pytesseract.TesseractNotFoundError()
    monkeypatch.setattr(pytesseract, "image_to_string", boom)
    with pytest.raises(RuntimeError, match="Tesseract"):
        extract_text_from_file(path, "image/png")
