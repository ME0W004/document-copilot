"""Generic (non-SEC) document ingestion via Docling.

Handles PDF, DOCX, HTML, and image files registered through the upload API
(app.api.documents) or the operator CLI (python -m ingest.generic). SEC
filings keep their dedicated pipeline (ingest.chunk_and_embed +
ingest.sec_tables); this module never rewrites it.

Pipeline: file → DocumentConverter (format-specific options, OCR wiring) →
DoclingDocument → existing HybridChunker → ChunkRecord → ingest.persist.
Chunk text stays canonical; search_text is derived downstream in
ingest.persist.write_chunks via app.text.normalize.

CLI:
    uv run python -m ingest.generic --file path/to/report.pdf
    uv run python -m ingest.generic --file path/to/report.pdf --language fa
    uv run python -m ingest.generic --file path/to/report.pdf --dry-run
    uv run python -m ingest.generic --file path/to/report.pdf --force
"""

from __future__ import annotations

import argparse
import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models import SourceDocument
from app.storage import resolve_stored_path, store_document_bytes
from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.datamodel.pipeline_options import (
    EasyOcrOptions,
    OcrOptions,
    PdfPipelineOptions,
    RapidOcrOptions,
    TesseractCliOcrOptions,
    TesseractOcrOptions,
)
from docling.document_converter import (
    DocumentConverter,
    ImageFormatOption,
    PdfFormatOption,
)
from ingest.chunking import ChunkRecord, build_hybrid_chunker, page_from_chunk_meta
from ingest.formats import DocumentFormat, detect_format, format_for_suffix
from ingest.persist import delete_chunks, document_has_chunks, write_chunks

_LANGUAGE_RE = re.compile(r"^[a-z]{2}(-[A-Za-z]{2,8})?$|^mixed$|^unknown$")

# DocumentFormat → docling InputFormat. IMAGE and PDF share the PDF pipeline,
# which is why both honor the OCR settings.
_INPUT_FORMATS: dict[DocumentFormat, InputFormat] = {
    DocumentFormat.PDF: InputFormat.PDF,
    DocumentFormat.DOCX: InputFormat.DOCX,
    DocumentFormat.HTML: InputFormat.HTML,
    DocumentFormat.IMAGE: InputFormat.IMAGE,
}

# Configurable OCR engines (docling option classes); selected by
# settings.ocr_engine. Engine availability differs per install —
# "rapidocr" ships with the docling dependency in this repo's lockfile,
# "tesseract_cli" needs a system tesseract binary, "easyocr" needs the
# docling[easyocr] extra.
_OCR_ENGINES: dict[str, type[OcrOptions]] = {
    "rapidocr": RapidOcrOptions,
    "tesseract_cli": TesseractCliOcrOptions,
    "tesseract": TesseractOcrOptions,
    "easyocr": EasyOcrOptions,
}


class ConversionError(RuntimeError):
    """Docling failed to convert the file (parser, OCR, or engine failure)."""


class EmptyDocumentError(RuntimeError):
    """The document converted but yielded no extractable text."""


def validate_language(value: str | None) -> str | None:
    """Validate the document language metadata ('fa', 'en', 'mixed', 'unknown')."""
    if value is None:
        return None
    if not _LANGUAGE_RE.match(value):
        raise ValueError(
            f"Invalid language {value!r}. Use an ISO 639-1 code, "
            "'mixed', or 'unknown'."
        )
    return value


def _ocr_options() -> OcrOptions:
    engine_cls = _OCR_ENGINES.get(settings.ocr_engine)
    if engine_cls is None:
        raise ValueError(
            f"Unknown OCR_ENGINE {settings.ocr_engine!r}. "
            f"Supported: {', '.join(sorted(_OCR_ENGINES))}"
        )
    if not settings.ocr_language_list:
        raise ValueError("OCR_LANGUAGES must list at least one language code.")
    return engine_cls(lang=settings.ocr_language_list)


def build_converter(format: DocumentFormat) -> DocumentConverter:
    """Converter restricted to the detected format, with OCR wiring for PDF/image."""
    input_format = _INPUT_FORMATS[format]
    format_options: dict[InputFormat, Any] = {}
    if format in (DocumentFormat.PDF, DocumentFormat.IMAGE):
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = settings.ocr_enabled
        if settings.ocr_enabled:
            pipeline_options.ocr_options = _ocr_options()
        option_cls = (
            PdfFormatOption if format is DocumentFormat.PDF else ImageFormatOption
        )
        format_options[input_format] = option_cls(pipeline_options=pipeline_options)
    return DocumentConverter(
        allowed_formats=[input_format],
        format_options=format_options,
    )


def convert_document(file_path: Path, format: DocumentFormat) -> Any:
    """Convert a file to a DoclingDocument, failing explicitly.

    Docling's PARTIAL_SUCCESS means some pages failed preprocessing/parsing;
    ingestion stops rather than silently indexing an incomplete document.
    """
    if format is DocumentFormat.IMAGE and not settings.ocr_enabled:
        raise ConversionError(
            "Image ingestion requires OCR (the image pipeline reads text via "
            "OCR only). Set OCR_ENABLED=true and configure an available engine."
        )

    try:
        result = build_converter(format).convert(file_path)
    except Exception as exc:
        raise ConversionError(
            f"Conversion of {file_path.name} failed ({type(exc).__name__}) "
            f"[format={format.value}, parser=docling, ocr_enabled={settings.ocr_enabled}, "
            f"ocr_engine={settings.ocr_engine}, ocr_languages={settings.ocr_languages}]: {exc}"
        ) from exc

    if result.status is not ConversionStatus.SUCCESS:
        errors = [getattr(error, "error_message", str(error)) for error in result.errors]
        raise ConversionError(
            f"Conversion of {file_path.name} ended in {result.status.value}: "
            + "; ".join(errors or ["no details reported"])
        )
    return result.document


def section_from_headings(meta: Any) -> str | None:
    """Headings-derived section path for generic documents (no fallbacks).

    SEC filings keep their Item-regex fallback in ingest.chunking; generic
    documents with no heading hierarchy get None rather than a fake section.
    """
    headings = getattr(meta, "headings", None) or []
    return " > ".join(headings) or None


def chunk_generic_document(
    doc: Any,
    format: DocumentFormat,
    *,
    title: str,
    language: str | None,
    max_chunks: int | None = None,
) -> list[ChunkRecord]:
    """Chunk a converted DoclingDocument with the existing HybridChunker."""
    chunker = build_hybrid_chunker()
    records: list[ChunkRecord] = []
    for index, chunk in enumerate(chunker.chunk(dl_doc=doc)):
        if max_chunks is not None and index >= max_chunks:
            break
        text = chunker.contextualize(chunk=chunk)
        if not text.strip():
            continue
        records.append(
            ChunkRecord(
                chunk_index=len(records),
                text=text,
                page=page_from_chunk_meta(chunk.meta),
                section=section_from_headings(chunk.meta),
                token_count=chunker.tokenizer.count_tokens(text),
                chunk_metadata={
                    "source_format": format.value,
                    "title": title,
                    "language": language,
                    "chunk_kind": "narrative",
                    "raw_text": chunk.text,
                    "docling_meta": chunk.meta.export_json_dict(),
                },
            )
        )

    # Fallback for documents that contain text (e.g. headings/titles/OCR text)
    # but yielded no body chunks from HybridChunker (common in single-page scans,
    # header-only documents, or short forms where all text is classified as headers).
    if not records and hasattr(doc, "texts") and doc.texts:
        items_by_page: dict[str | None, list[Any]] = {}
        for item in doc.texts:
            item_text = getattr(item, "text", "")
            if not item_text or not item_text.strip():
                continue
            item_page = None
            if format is not DocumentFormat.DOCX:
                for entry in getattr(item, "prov", []) or []:
                    page_no = getattr(entry, "page_no", None)
                    if page_no is not None:
                        item_page = str(page_no)
                        break
            items_by_page.setdefault(item_page, []).append(item)

        for page_key, page_items in items_by_page.items():
            if max_chunks is not None and len(records) >= max_chunks:
                break
            combined_text = "\n\n".join(
                getattr(item, "text", "").strip()
                for item in page_items
                if getattr(item, "text", "").strip()
            )
            if not combined_text.strip():
                continue
            first_item = page_items[0]
            first_label = str(getattr(first_item, "label", "")).lower()
            section_title = (
                getattr(first_item, "text", None)
                if "header" in first_label or "title" in first_label
                else None
            )
            records.append(
                ChunkRecord(
                    chunk_index=len(records),
                    text=combined_text,
                    page=page_key,
                    section=section_title,
                    token_count=chunker.tokenizer.count_tokens(combined_text),
                    chunk_metadata={
                        "source_format": format.value,
                        "title": title,
                        "language": language,
                        "chunk_kind": "narrative",
                        "raw_text": combined_text,
                        "docling_meta": {
                            "fallback": "header_only_content",
                            "item_count": len(page_items),
                        },
                    },
                )
            )

    return records


@dataclass(frozen=True, slots=True)
class GenericIngestResult:
    document: SourceDocument
    chunks_written: int
    deduplicated: bool


def ingest_file(
    session: Session,
    file_path: Path,
    *,
    relative_path: str,
    title: str | None = None,
    language: str | None = None,
    max_chunks: int | None = None,
    dry_run: bool = False,
    skip_existing: bool = True,
    force: bool = False,
) -> GenericIngestResult:
    """Register and ingest one generic file already stored on disk.

    Dedup identity is the SHA-256 content hash: re-registering identical
    bytes returns the existing document instead of creating duplicates.
    The document row and its chunks commit together in write_chunks; any
    conversion, OCR, embedding, or write failure leaves the session
    uncommitted so the caller's rollback removes the half-registered row.
    """
    format = detect_format(file_path)
    language = validate_language(language)
    resolved_title = (title or file_path.stem)[:255]
    content_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()

    existing = session.scalar(
        select(SourceDocument).where(SourceDocument.content_hash == content_hash)
    )
    if existing is not None:
        if skip_existing and not force and document_has_chunks(session, existing.id):
            return GenericIngestResult(
                document=existing, chunks_written=0, deduplicated=True
            )
        if force and not dry_run:
            delete_chunks(session, existing.id)

    print(f"Chunking {file_path.name} ({format.value})...")
    doc = convert_document(file_path, format)
    records = chunk_generic_document(
        doc,
        format,
        title=resolved_title,
        language=language,
        max_chunks=max_chunks,
    )
    if not records:
        raise EmptyDocumentError(
            "Document converted but produced no extractable text. If it is a "
            "scanned document, enable OCR (OCR_ENABLED=true) and retry."
        )
    max_tokens = max(record.token_count for record in records)
    print(f"  {len(records)} chunk(s), max_tokens={max_tokens}")

    if dry_run:
        sample = records[0]
        print(f"  sample page={sample.page!r} section={sample.section!r}")
        print(f"  sample preview={sample.text[:120]!r}")
        return GenericIngestResult(
            document=existing or SourceDocument(
                source_format=format.value,
                title=resolved_title,
                language=language,
                file_path=relative_path,
                content_hash=content_hash,
            ),
            chunks_written=len(records),
            deduplicated=False,
        )

    if existing is not None:
        document = existing
        document.title = document.title or resolved_title
        document.language = document.language or language
        document.file_path = relative_path
    else:
        document = SourceDocument(
            source_format=format.value,
            title=resolved_title,
            language=language,
            file_path=relative_path,
            content_hash=content_hash,
            ingested_at=datetime.now(UTC),
        )
        session.add(document)
        session.flush()

    written = write_chunks(session, document, records)
    # write_chunks committed; reload so server-side defaults (created_at) are
    # available to the caller's response.
    session.refresh(document)
    return GenericIngestResult(
        document=document, chunks_written=written, deduplicated=False
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="Path to the document file")
    parser.add_argument(
        "--title", default=None, help="Display title (default: filename stem)"
    )
    parser.add_argument(
        "--language", default=None, help="Language metadata: fa, en, mixed, unknown"
    )
    parser.add_argument(
        "--max-chunks", type=int, default=None, help="Cap chunks per document (smoke test)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Chunk only; no embeddings or database writes"
    )
    parser.add_argument(
        "--skip-existing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip files whose content hash is already ingested (default: true)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete existing chunks for the matched document before re-ingesting",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    source = Path(args.file)
    if not source.is_file():
        raise SystemExit(f"File not found: {source}")
    format_for_suffix(source.suffix)  # fail before copying unsupported files

    stored = store_document_bytes(source.read_bytes(), source.suffix.lower())
    print(f"Stored {source.name} as {stored.relative_path}")

    engine = create_engine(settings.sqlalchemy_database_url)
    with Session(engine) as session:
        result = ingest_file(
            session,
            resolve_stored_path(stored.relative_path),
            relative_path=stored.relative_path,
            title=args.title,
            language=args.language,
            max_chunks=args.max_chunks,
            dry_run=args.dry_run,
            skip_existing=args.skip_existing,
            force=args.force,
        )

    if result.deduplicated:
        print(f"Document already ingested (content hash match): {result.document.id}")
        return
    if args.dry_run:
        print(f"Dry run: {result.chunks_written} chunk(s) produced, nothing written")
        return
    print(
        f"Done: document {result.document.id}, "
        f"{result.chunks_written} chunk(s) written"
    )


if __name__ == "__main__":
    main()
