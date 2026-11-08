"""Unit tests for the generic (non-SEC) ingestion path.

Docling conversion is mocked at the module boundary; the real converter is
exercised by test_generic_integration.py.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.config import settings
from app.database.models import DocumentChunk, SourceDocument
from app.text.normalize import normalize
from docling.datamodel.base_models import InputFormat
from ingest.chunking import ChunkRecord
from ingest.formats import DocumentFormat
from ingest.generic import (
    ConversionError,
    EmptyDocumentError,
    build_converter,
    convert_document,
    ingest_file,
    section_from_headings,
    validate_language,
)

# ---------------------------------------------------------------- language


@pytest.mark.parametrize("value", ["fa", "en", "mixed", "unknown", None, "pt-br"])
def test_validate_language_accepts_documented_values(value: str | None) -> None:
    assert validate_language(value) == value


@pytest.mark.parametrize("value", ["FARSI", "farsi", "f a", "", "fa_IR!"])
def test_validate_language_rejects_unknown_values(value: str) -> None:
    with pytest.raises(ValueError):
        validate_language(value)


# ------------------------------------------------------------- sections


def test_section_from_headings_joins_hierarchy() -> None:
    meta = SimpleNamespace(headings=["Chapter One", "Risks"])
    assert section_from_headings(meta) == "Chapter One > Risks"


@pytest.mark.parametrize("headings", [None, []])
def test_section_from_headings_returns_none_without_headings(headings: list | None) -> None:
    assert section_from_headings(SimpleNamespace(headings=headings)) is None


# ------------------------------------------------------ converter options


def test_build_converter_disables_ocr_by_default(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ocr_enabled", False)

    converter = build_converter(DocumentFormat.PDF)
    options = converter.format_to_options[InputFormat.PDF].pipeline_options

    assert options.do_ocr is False
    assert converter.allowed_formats == [InputFormat.PDF]


def test_build_converter_wires_ocr_engine_and_languages(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ocr_enabled", True)
    monkeypatch.setattr(settings, "ocr_engine", "tesseract_cli")
    monkeypatch.setattr(settings, "ocr_languages", "fas,eng")

    converter = build_converter(DocumentFormat.PDF)
    options = converter.format_to_options[InputFormat.PDF].pipeline_options

    assert options.do_ocr is True
    assert options.ocr_options.lang == ["fas", "eng"]


def test_build_converter_rejects_unknown_ocr_engine(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ocr_enabled", True)
    monkeypatch.setattr(settings, "ocr_engine", "hal_9000")

    with pytest.raises(ValueError, match="hal_9000"):
        build_converter(DocumentFormat.PDF)


def test_convert_document_rejects_images_without_ocr(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ocr_enabled", False)
    image = tmp_path / "scan.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nstub")

    with pytest.raises(ConversionError, match="requires OCR"):
        convert_document(image, DocumentFormat.IMAGE)


# ------------------------------------------------------------ ingest_file


def _record(index: int) -> ChunkRecord:
    text = f"chunk {index} text"
    return ChunkRecord(
        chunk_index=index,
        text=text,
        page="1",
        section=None,
        token_count=10,
        chunk_metadata={
            "source_format": "pdf",
            "title": "Sample Document Title",
            "language": "en",
            "chunk_kind": "narrative",
            "raw_text": text,
            "docling_meta": {},
        },
    )


@pytest.fixture
def pdf_file(tmp_path):
    file = tmp_path / "report.pdf"
    file.write_bytes(b"%PDF-1.4 stub pdf content")
    return file


def _patch_pipeline(records: list[ChunkRecord]):
    """Bypass real conversion/chunking/embedding; return the mocks."""
    return (
        patch("ingest.generic.convert_document", return_value=object()),
        patch("ingest.generic.chunk_generic_document", return_value=records),
        patch(
            "ingest.persist.embed_texts",
            side_effect=lambda texts, **_: [[0.0] * 8 for _ in texts],
        ),
    )


def test_ingest_file_registers_document_and_writes_chunks(pdf_file) -> None:
    session = MagicMock()
    session.scalar.return_value = None  # no document with this content hash
    records = [_record(0), _record(1)]
    patches = _patch_pipeline(records)

    with patches[0], patches[1], patches[2]:
        result = ingest_file(
            session,
            pdf_file,
            relative_path="report.pdf",
            title="Sample Document Title",
            language="en",
        )

    document = result.document
    assert result.chunks_written == 2
    assert result.deduplicated is False
    assert isinstance(document, SourceDocument)
    assert document.source_format == "pdf"
    assert document.title == "Sample Document Title"
    assert document.language == "en"
    assert document.file_path == "report.pdf"
    assert len(document.content_hash) == 64
    assert document.accession_number is None  # no fake SEC metadata
    assert document.ticker is None
    added = [call.args[0] for call in session.add.call_args_list]
    assert any(isinstance(obj, SourceDocument) for obj in added)
    assert sum(isinstance(obj, DocumentChunk) for obj in added) == 2
    session.commit.assert_called_once()


def test_ingest_file_defaults_title_to_filename_stem(pdf_file) -> None:
    session = MagicMock()
    session.scalar.return_value = None
    patches = _patch_pipeline([_record(0)])

    with patches[0], patches[1], patches[2]:
        result = ingest_file(session, pdf_file, relative_path="report.pdf")

    assert result.document.title == "report"


def test_ingest_file_deduplicates_on_content_hash(pdf_file) -> None:
    session = MagicMock()
    existing = SourceDocument(
        id=uuid.uuid4(),
        source_format="pdf",
        title="Sample Document Title",
        file_path="report.pdf",
        content_hash="a" * 64,
    )
    # First scalar (content-hash lookup) finds the document; the same mock
    # makes document_has_chunks truthy, so the dedup path triggers.
    session.scalar.return_value = existing

    result = ingest_file(session, pdf_file, relative_path="report.pdf")

    assert result.document is existing
    assert result.deduplicated is True
    assert result.chunks_written == 0
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_ingest_file_force_reingests_existing_document(pdf_file) -> None:
    session = MagicMock()
    existing = SourceDocument(
        id=uuid.uuid4(),
        source_format="pdf",
        title="Sample Document Title",
        file_path="report.pdf",
        content_hash="a" * 64,
    )
    session.scalar.return_value = existing
    records = [_record(0)]
    patches = _patch_pipeline(records)

    with patches[0], patches[1], patches[2]:
        result = ingest_file(
            session, pdf_file, relative_path="report.pdf", force=True
        )

    assert result.document is existing
    assert result.chunks_written == 1
    session.execute.assert_called()  # delete_chunks ran


def test_ingest_file_fails_explicitly_on_empty_document(pdf_file) -> None:
    session = MagicMock()
    session.scalar.return_value = None
    patches = _patch_pipeline([])

    with patches[0], patches[1], patches[2]:
        with pytest.raises(EmptyDocumentError):
            ingest_file(session, pdf_file, relative_path="report.pdf")


def test_ingest_file_maps_conversion_failure(pdf_file) -> None:
    session = MagicMock()
    session.scalar.return_value = None

    with (
        patch(
            "ingest.generic.convert_document",
            side_effect=ConversionError("Conversion of report.pdf ended in failure"),
        ),
        pytest.raises(ConversionError),
    ):
        ingest_file(session, pdf_file, relative_path="report.pdf")


def test_ingest_file_dry_run_writes_nothing(pdf_file) -> None:
    session = MagicMock()
    session.scalar.return_value = None
    patches = _patch_pipeline([_record(0)])

    with patches[0], patches[1], patches[2]:
        result = ingest_file(
            session, pdf_file, relative_path="report.pdf", dry_run=True
        )

    assert result.chunks_written == 1
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_ingest_file_rejects_invalid_language(pdf_file) -> None:
    session = MagicMock()
    session.scalar.return_value = None

    with pytest.raises(ValueError, match="language"):
        ingest_file(
            session, pdf_file, relative_path="report.pdf", language="Farsi"
        )


# ---------------------------------------------- normalization contract pin


def test_write_chunks_keeps_canonical_text_and_derives_search_text(pdf_file) -> None:
    """chunk.text stays canonical; search_text == normalize(chunk.text)."""
    from ingest.persist import write_chunks

    session = MagicMock()
    document = SourceDocument(id=uuid.uuid4(), source_format="pdf")
    text = "Invoice  ۲۰۲۴ — میزان ریسک‌های بازار"
    records = [
        ChunkRecord(
            chunk_index=0,
            text=text,
            page="1",
            section=None,
            token_count=10,
            chunk_metadata={},
        )
    ]

    with patch(
        "ingest.persist.embed_texts",
        side_effect=lambda texts, **_: [[0.0] * 8 for _ in texts],
    ):
        written = write_chunks(session, document, records)

    assert written == 1
    chunk = session.add.call_args.args[0]
    assert chunk.text == text  # canonical text untouched
    assert chunk.search_text == normalize(text)
    assert chunk.document_id == document.id
    assert chunk.page == "1"
