"""Integration tests: real Docling conversion of bundled fixtures.

Marked `integration` per repo convention; unlike the credential-gated suites,
these only need the Docling layout model (downloaded from HuggingFace on
first run and cached). They hit no database and no LLM/embedding API.

The OCR-dependent test (scanned document) requires an OCR engine; none is
installable in the current environment (RapidOCR model host unreachable,
no tesseract binary), so it is marked with `ocr` and reported NOT RUN.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import settings
from docling.datamodel.base_models import ConversionStatus
from ingest.chunking import CHUNK_MAX_TOKENS
from ingest.formats import DocumentFormat
from ingest.generic import (
    ConversionError,
    build_converter,
    chunk_generic_document,
    convert_document,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def disable_ocr(monkeypatch):
    monkeypatch.setattr(settings, "ocr_enabled", False)


def test_configured_converter_reads_digital_pdf_fixture() -> None:
    # Uses the app's converter wiring (OCR off by default). A raw
    # DocumentConverter() defaults to OCR-on and would initialize the
    # RapidOCR engine, which downloads models from modelscope.cn.
    result = build_converter(DocumentFormat.PDF).convert(FIXTURES / "sample.pdf")
    assert result.status is ConversionStatus.SUCCESS


def test_pdf_path_extracts_text_and_pages() -> None:
    doc = convert_document(FIXTURES / "sample.pdf", DocumentFormat.PDF)
    records = chunk_generic_document(
        doc, DocumentFormat.PDF, title="Sample Document Title", language="en"
    )

    assert records, "digital PDF must produce chunks"
    assert any("digital PDF fixture" in record.text for record in records)
    assert {record.page for record in records} == {"1"}
    assert all(record.chunk_metadata["source_format"] == "pdf" for record in records)
    assert all(record.chunk_metadata["title"] == "Sample Document Title" for record in records)
    assert all(0 < record.token_count <= CHUNK_MAX_TOKENS for record in records)


def test_docx_path_extracts_text_and_headings() -> None:
    doc = convert_document(FIXTURES / "sample.docx", DocumentFormat.DOCX)
    records = chunk_generic_document(
        doc, DocumentFormat.DOCX, title="Sample Document Title", language="en"
    )

    assert records
    assert any("sample DOCX document" in record.text for record in records)
    # DOCX has no page concept: provenance must stay None, never faked.
    assert all(record.page is None for record in records)
    assert all(record.chunk_metadata["source_format"] == "docx" for record in records)


def test_html_path_ingests_generic_html(tmp_path: Path) -> None:
    html = tmp_path / "note.html"
    html.write_text(
        "<html><body><h1>Heading One</h1><p>Generic HTML body text for the "
        "ingestion path.</p></body></html>",
        encoding="utf-8",
    )

    doc = convert_document(html, DocumentFormat.HTML)
    records = chunk_generic_document(
        doc, DocumentFormat.HTML, title="note", language="en"
    )

    assert records
    assert any("Generic HTML body text" in record.text for record in records)
    assert all(record.page is None for record in records)


def test_corrupted_pdf_fails_explicitly(tmp_path: Path) -> None:
    corrupt = tmp_path / "corrupt.pdf"
    corrupt.write_bytes(b"%PDF-1.4 this file is truncated and has no pages")

    with pytest.raises(ConversionError):
        convert_document(corrupt, DocumentFormat.PDF)


def test_scanned_pdf_ocr_path_placeholder() -> None:
    """Placeholder documenting the OCR integration gap.

    With OCR_ENABLED=true and an installed engine, convert_document on a
    scanned fixture would exercise the OCR path. This environment has no
    runnable engine (RapidOCR models unreachable, no tesseract binary), so
    the real OCR test is intentionally not implemented — results must not
    be faked. See docs/sprint-4-report.md §19.
    """
    pytest.skip("No OCR engine available in this environment (NOT RUN)")
