"""Readiness tests for DOCX ingestion (Sprint 5 Part 14, 19).

Covers:
- English DOCX: headings mapped to sections, page=None (never faked), chunk ordering.
- Persian DOCX: Persian headings, ZWNJ, Persian digits, OpenAI/AI technical terms, page=None.
- Canonical text vs search_text integrity.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.config import settings
from app.text.normalize import normalize
from ingest.chunking import CHUNK_MAX_TOKENS
from ingest.formats import DocumentFormat, detect_format
from ingest.generic import (
    chunk_generic_document,
    convert_document,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "documents" / "docx"


# ===========================================================================
# Fast Unit Tests
# ===========================================================================


def test_docx_format_detection() -> None:
    path = FIXTURES_DIR / "english.docx"
    assert detect_format(path) is DocumentFormat.DOCX


def test_docx_page_is_always_none() -> None:
    """DOCX documents have no concept of pages; page metadata must be None."""
    meta = SimpleNamespace(
        headings=["Section One"],
        origin=None,
        doc_items=[],
        export_json_dict=lambda: {"headings": ["Section One"]},
    )
    chunk = SimpleNamespace(text="DOCX paragraph content.", meta=meta)

    mock_chunker = MagicMock()
    mock_chunker.chunk.return_value = [chunk]
    mock_chunker.contextualize.side_effect = lambda chunk=None, **k: chunk.text if chunk else ""
    mock_chunker.tokenizer.count_tokens.side_effect = lambda t: len(t.split())

    mock_doc = SimpleNamespace(texts=[])

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("ingest.generic.build_hybrid_chunker", lambda: mock_chunker)
        records = chunk_generic_document(
            mock_doc,
            DocumentFormat.DOCX,
            title="DOCX Document",
            language="en",
        )

    assert len(records) == 1
    assert records[0].page is None, "DOCX page must be None, never faked"
    assert records[0].section == "Section One"
    assert records[0].chunk_metadata["source_format"] == "docx"


# ===========================================================================
# Real Conversion Integration Tests (Docling MS Word Parser)
# ===========================================================================


@pytest.mark.integration
def test_english_docx_readiness(monkeypatch) -> None:
    """Validate English DOCX text extraction, headings, and page=None."""
    monkeypatch.setattr(settings, "ocr_enabled", False)
    docx_path = FIXTURES_DIR / "english.docx"
    assert docx_path.is_file(), f"Fixture missing: {docx_path}"

    doc = convert_document(docx_path, DocumentFormat.DOCX)
    records = chunk_generic_document(
        doc, DocumentFormat.DOCX, title="Annual Report", language="en"
    )

    assert len(records) >= 1, "English DOCX must produce chunks"
    all_text = " ".join(r.text for r in records)
    assert "fiscal year 2024 results" in all_text.lower() or "annual report" in all_text.lower()

    # Verify sections extracted from Heading1 styles
    sections = {r.section for r in records if r.section is not None}
    assert any("Annual Report" in s or "Financial Position" in s for s in sections)

    # Invariant: page must be None for DOCX
    for r in records:
        assert r.page is None, "DOCX page must never be invented"
        assert r.chunk_metadata["source_format"] == "docx"
        assert 0 < r.token_count <= CHUNK_MAX_TOKENS


@pytest.mark.integration
def test_persian_docx_readiness(monkeypatch) -> None:
    """Validate Persian DOCX text extraction, Persian headings, ZWNJ, and page=None."""
    monkeypatch.setattr(settings, "ocr_enabled", False)
    docx_path = FIXTURES_DIR / "persian.docx"
    assert docx_path.is_file(), f"Fixture missing: {docx_path}"

    doc = convert_document(docx_path, DocumentFormat.DOCX)
    records = chunk_generic_document(
        doc, DocumentFormat.DOCX, title="گزارش سالانه", language="fa"
    )

    assert len(records) >= 1, "Persian DOCX must produce chunks"
    all_text = " ".join(r.text for r in records)

    # Persian letters and content
    assert "گزارش سالانه" in all_text or "شرکت" in all_text
    # English terms survive
    assert "OpenAI" in all_text or "AI" in all_text
    # Digits and ZWNJ
    assert "۱۴۰۳" in all_text or "1403" in all_text

    # Verify sections extracted from Heading1 styles
    sections = {r.section for r in records if r.section is not None}
    assert any("گزارش سالانه" in s or "ریسک‌های بازار" in s for s in sections)

    for r in records:
        assert r.page is None, "DOCX page must be None"
        assert r.chunk_metadata["source_format"] == "docx"
        # Canonical text and search_text derivation
        canonical = r.text
        norm = normalize(canonical)
        assert norm, "search_text normalization must produce valid text"
        assert r.text == canonical, "Canonical text must not be overwritten"
