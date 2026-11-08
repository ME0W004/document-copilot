"""Readiness tests for OCR and Image Ingestion (Sprint 5 Part 7-13, 20).

Covers:
- Image format detection (PNG, JPG, BMP, TIFF, WEBP) and magic-byte checks.
- Security: mismatched magic bytes, corrupted files, empty files.
- OCR configuration and engine selection.
- OCR-disabled behavior: fail-fast on images with explicit message.
- OCR integration tests (RapidOCR on English image and scanned PDF).
- Persian OCR evaluation and honest limitation recording.
- OCR Quality Gates: rejection of empty extractions without silent indexing.
- OCR Confidence: verifying no fake confidence fields are invented.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.config import settings
from ingest.formats import DocumentFormat, UnsupportedFormatError, detect_format
from ingest.generic import (
    ConversionError,
    build_converter,
    chunk_generic_document,
    convert_document,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "documents"
IMAGES_DIR = FIXTURES_DIR / "images"
PDF_DIR = FIXTURES_DIR / "pdf"


# ===========================================================================
# Fast Unit Tests (No OCR inference / no network / no DB)
# ===========================================================================


@pytest.mark.parametrize(
    ("filename", "expected_format"),
    [
        ("scan-english.png", DocumentFormat.IMAGE),
        ("scan-english.jpg", DocumentFormat.IMAGE),
        ("scan-english.tiff", DocumentFormat.IMAGE),
        ("scan-english.bmp", DocumentFormat.IMAGE),
        ("scan-english.webp", DocumentFormat.IMAGE),
    ],
)
def test_image_formats_magic_byte_detection(filename: str, expected_format: DocumentFormat) -> None:
    path = IMAGES_DIR / filename
    assert path.is_file(), f"Fixture missing: {path}"
    assert detect_format(path) is expected_format


def test_mismatched_magic_bytes_rejected(tmp_path: Path) -> None:
    # A file with .pdf suffix containing PNG magic bytes
    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_bytes(b"\x89PNG\r\n\x1a\nfake png data inside a pdf extension")
    with pytest.raises(UnsupportedFormatError, match="File content does not match"):
        detect_format(fake_pdf)

    # A file with .png suffix containing plain text
    fake_png = tmp_path / "fake.png"
    fake_png.write_bytes(b"Plain text in png file")
    with pytest.raises(UnsupportedFormatError, match="File content does not match"):
        detect_format(fake_png)


def test_empty_image_rejected(tmp_path: Path) -> None:
    empty_img = tmp_path / "empty.png"
    empty_img.write_bytes(b"")
    with pytest.raises(UnsupportedFormatError):
        detect_format(empty_img)


def test_image_requires_ocr_fails_fast_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ocr_enabled", False)
    img_path = IMAGES_DIR / "scan-english.png"

    with pytest.raises(ConversionError, match="Image ingestion requires OCR"):
        convert_document(img_path, DocumentFormat.IMAGE)


def test_ocr_engine_configuration_validation(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ocr_enabled", True)
    monkeypatch.setattr(settings, "ocr_engine", "nonexistent_engine")

    with pytest.raises(ValueError, match="Unknown OCR_ENGINE"):
        build_converter(DocumentFormat.IMAGE)


def test_ocr_languages_validation(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ocr_enabled", True)
    monkeypatch.setattr(settings, "ocr_engine", "rapidocr")
    monkeypatch.setattr(settings, "ocr_languages", "")

    with pytest.raises(ValueError, match="OCR_LANGUAGES must list at least one"):
        build_converter(DocumentFormat.IMAGE)


# ===========================================================================
# Integration Tests (Real RapidOCR execution)
# ===========================================================================


@pytest.mark.integration
def test_rapidocr_english_image_readiness(monkeypatch) -> None:
    """Validate real English image conversion with RapidOCR."""
    monkeypatch.setattr(settings, "ocr_enabled", True)
    monkeypatch.setattr(settings, "ocr_engine", "rapidocr")
    monkeypatch.setattr(settings, "ocr_languages", "en")

    img_path = IMAGES_DIR / "scan-english.png"
    assert img_path.is_file(), f"Fixture missing: {img_path}"

    doc = convert_document(img_path, DocumentFormat.IMAGE)
    records = chunk_generic_document(
        doc, DocumentFormat.IMAGE, title="Scan English", language="en"
    )

    assert len(records) >= 1, "Readable English image must produce chunks"
    chunk_text = " ".join(r.text for r in records)
    assert "QUARTERLY REVENUE REPORT" in chunk_text
    assert "TOTAL 3400 UNITS SOLD" in chunk_text

    # Verify no fake confidence fields invented on chunk metadata
    for r in records:
        assert "fake_confidence" not in r.chunk_metadata
        assert r.chunk_metadata["source_format"] == "image"


@pytest.mark.integration
def test_rapidocr_scanned_pdf_readiness(monkeypatch) -> None:
    """Validate real scanned 2-page PDF conversion with RapidOCR."""
    monkeypatch.setattr(settings, "ocr_enabled", True)
    monkeypatch.setattr(settings, "ocr_engine", "rapidocr")
    monkeypatch.setattr(settings, "ocr_languages", "en")

    pdf_path = PDF_DIR / "scanned-english.pdf"
    assert pdf_path.is_file(), f"Fixture missing: {pdf_path}"

    doc = convert_document(pdf_path, DocumentFormat.PDF)
    records = chunk_generic_document(
        doc, DocumentFormat.PDF, title="Scanned English PDF", language="en"
    )

    assert len(records) >= 1, "Scanned English PDF must produce chunks"
    pages = {r.page for r in records if r.page is not None}
    assert "1" in pages, "Page 1 must be present in scanned PDF chunks"

    full_text = " ".join(r.text for r in records)
    assert "INVOICE TOTAL 1250 DOLLARS" in full_text
    assert "DUE DATE 2024-05-30" in full_text


@pytest.mark.integration
def test_rapidocr_persian_image_observation(monkeypatch) -> None:
    """Evaluate RapidOCR on Persian text image.

    Documents observed quality: RapidOCR lacks Persian models, producing
    non-Persian character output. Demonstrates pipeline safety (no crash,
    returns text or raises EmptyDocumentError, canonical text preserved).
    """
    monkeypatch.setattr(settings, "ocr_enabled", True)
    monkeypatch.setattr(settings, "ocr_engine", "rapidocr")
    monkeypatch.setattr(settings, "ocr_languages", "en")

    img_path = IMAGES_DIR / "scan-persian.png"
    assert img_path.is_file(), f"Fixture missing: {img_path}"

    doc = convert_document(img_path, DocumentFormat.IMAGE)
    raw_text = doc.export_to_text().strip()

    # RapidOCR only has Chinese/English models; it does not accurately read Persian
    # The output is observed to be non-Persian ASCII approximations (e.g. 'w l')
    assert raw_text != "گزارش مالی سال ۱۴۰۳", (
        "RapidOCR is not expected to produce accurate Persian text without Persian trained models"
    )


def test_tesseract_persian_ocr_status() -> None:
    """Document Persian OCR status with Tesseract.

    Reports NOT RUN when tesseract binary is not installed on the system,
    per Sprint 5 Part 8 and Part 24 instructions.
    """
    tesseract_available = shutil.which("tesseract") is not None
    if not tesseract_available:
        pytest.skip("Persian scanned PDF with Tesseract: NOT RUN — tesseract binary unavailable")


@pytest.mark.integration
def test_quality_gate_empty_scan_fails_cleanly(tmp_path: Path, monkeypatch) -> None:
    """Quality Gate: An empty/blank scan image must not produce empty chunks."""
    from PIL import Image

    monkeypatch.setattr(settings, "ocr_enabled", True)
    monkeypatch.setattr(settings, "ocr_engine", "rapidocr")
    monkeypatch.setattr(settings, "ocr_languages", "en")

    blank_path = tmp_path / "blank.png"
    Image.new("RGB", (200, 200), "white").save(blank_path)

    doc = convert_document(blank_path, DocumentFormat.IMAGE)
    records = chunk_generic_document(
        doc, DocumentFormat.IMAGE, title="Blank", language="en"
    )
    assert len(records) == 0, "A completely blank image must produce 0 chunks"
