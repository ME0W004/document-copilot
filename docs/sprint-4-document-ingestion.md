# Sprint 4 — Multi-Format Document Ingestion

Status: implemented on the `development` snapshot (2026-09-12). Companion report: `docs/sprint-4-report.md`.

---

## 1. Existing ingestion architecture (unchanged baseline)

Sprint 4 starts from the SEC-only pipeline:

```text
data/markdown/manifest.json (accession → local HTML path)
  → ingest/load_source_documents.py   registers source_documents rows (SEC metadata + markdown_content)
  → ingest/chunk_and_embed.py         per accession: skip/force logic, chunking, embedding, persistence
      → ingest/chunking.py            Docling DocumentConverter → HybridChunker (512 tokens, cl100k_base)
      → ingest/sec_tables.py          SEC table extraction (HTMLParser + SEC/XBRL regexes) → row chunks + document_tables
      → ingest/persist.py             NEW: shared embed → search_text=normalize(text) → document_chunks (+ document_tables) → commit
```

SEC-specific pieces: manifest discovery, accession lookup, `_filing_metadata`,
the `Item \d` section fallback, and `sec_tables`. Generic pieces (already
reusable before Sprint 4): HybridChunker, page provenance, normalize(),
OpenAI embeddings, DocumentChunk persistence.

## 2. Format dispatcher

`backend/ingest/formats.py`:

- `DocumentFormat`: `pdf | docx | html | image`.
- `format_for_suffix(suffix)` maps the extension (`SUPPORTED_EXTENSIONS`).
- `detect_format(path)` verifies content with magic bytes where a signature
  exists — `%PDF-` (PDF), `PK\x03\x04` (DOCX OPC zip), image signatures
  (PNG/JPEG/BMP/TIFF/RIFF-WEBP). HTML has no usable signature; its extension
  is authoritative. A file whose content contradicts its extension is
  rejected (`UnsupportedFormatError`).

SEC files never pass through the dispatcher: they resolve via the manifest by
accession number. Uploads (API/CLI) always go to the generic pipeline.

```text
SEC HTML (manifest accession)  → existing SEC pipeline (unchanged)
generic PDF/DOCX/HTML/image    → generic Docling pipeline (ingest/generic.py)
```

## 3. Supported formats

| Format | Parser | Page metadata | Notes |
| --- | --- | --- | --- |
| SEC HTML | existing `chunking.chunk_document` + `sec_tables` | provenance (mostly None) | untouched |
| Generic HTML | Docling `DocumentConverter` (default options) | `None` | |
| PDF | Docling PDF pipeline (`pypdfium2` backend + heron layout model) | real page provenance | OCR optional via settings |
| DOCX | Docling MS Word backend | `None` (never faked) | |
| Scanned PDF | Docling PDF pipeline + OCR engine | real | requires `OCR_ENABLED=true` + a working engine |
| Image (PNG/JPEG/TIFF/BMP/WEBP) | Docling image pipeline | `None` | OCR is mandatory for images; rejected explicitly when OCR is disabled |

## 4. Generic ingestion pipeline

`backend/ingest/generic.py`:

```text
file → detect_format → DocumentConverter (format-specific options)
     → DoclingDocument → existing HybridChunker (unchanged, 512 tokens)
     → ChunkRecord (generic chunk_metadata) → ingest.persist.write_chunks
```

- `build_converter(format)` restricts `allowed_formats` to the detected
  format and wires `PdfPipelineOptions` (PDF and IMAGE share the PDF
  pipeline, so both honor the OCR settings).
- `convert_document` fails explicitly: engine/parser exceptions become
  `ConversionError`; `PARTIAL_SUCCESS` (some pages failed) is treated as a
  failure — no silently incomplete corpus.
- `chunk_generic_document` reuses `build_hybrid_chunker()`; sections come
  from Docling heading hierarchy only (`section_from_headings`, no Item
  fallback, no fake sections); pages come from `page_from_chunk_meta`.
- Empty extraction raises `EmptyDocumentError` (the retry hint suggests
  enabling OCR for scanned inputs).

## 5. PDF ingestion

Digital PDFs: text layer extracted by Docling, chunks built with the existing
chunker, `page` populated from Docling provenance (verified: single-page
fixture → all chunks `page="1"`). Document metadata (title) is provided by
the caller (API form field or CLI `--title`, defaulting to the filename
stem). Tables remain inline markdown via the existing
`MarkdownTableSerializerProvider` — the SEC table extractor is not applied to
generic documents.

`PARTIAL_SUCCESS` (e.g. one page fails preprocessing) aborts ingestion with
the per-page error messages. Deliberately strict: grounding quality requires
complete documents.

## 6. DOCX ingestion

Docling MS Word backend; paragraphs/headings/lists/tables flow through the
same hybrid chunker. Page is always `None` (no page concept). Headings map to
section metadata only when Docling's backend recognizes them (real Word
styles); otherwise `section=None`.

## 7. OCR path

OCR applies to PDF (bitmap/scanned pages) and images through Docling's
pipeline options:

- `OCR_ENABLED` (default `false`) turns OCR on/off.
- `OCR_ENGINE` selects the engine: `rapidocr` (default; ships in this
  lockfile's dependency tree; downloads models from modelscope.cn on first
  use), `tesseract_cli` (requires a system tesseract binary), `easyocr`
  (requires the `docling[easyocr]` extra), `tesseract` (pytesseract wrapper).
- `OCR_LANGUAGES` is a comma-separated list; values are engine-specific —
  ISO 639-2 codes for tesseract (`eng`, `fas`), language families for
  rapidocr (`ch`, `en`).

Unknown engine values fail fast (`ValueError`) at converter build time.
Engine/model availability is validated only at conversion time — an OCR
failure surfaces as `ConversionError` (never a silent success).

Observed limitation: in this environment no OCR engine is runnable
(RapidOCR's modelscope host unreachable, no tesseract binary), so the OCR
path is validated by unit tests (options wiring, explicit failures) and its
integration test is reported NOT RUN.

## 8. Image ingestion

Direct image ingestion **is** cleanly supported by docling 2.96
(`InputFormat.IMAGE`: jpg/jpeg/png/tif/tiff/bmp/webp) and is implemented
through the same converter + chunker. Because docling's image pipeline reads
text via OCR only, `convert_document` rejects images up front when
`OCR_ENABLED=false` with an explicit message — no fake capability, no new
dependency.

## 9. Metadata model

`source_documents` now carries two shapes (one migration, one table):

| Column | SEC row | Generic row |
| --- | --- | --- |
| `source_format` (NOT NULL, default `sec_html`) | `sec_html` | `pdf` / `docx` / `html` / `image` |
| `title` | NULL | required (form field or filename stem) |
| `language` | NULL | optional (`fa`, `en`, ISO 639-1, `mixed`, `unknown`) |
| `file_path` | NULL | path relative to `DOCUMENT_STORAGE_DIR` |
| `content_hash` | NULL | SHA-256 of stored bytes |
| ticker / cik / company_name / form / filing_date / report_date / fiscal_year / accession_number / primary_document / source_url | filled | **NULL — never faked** (all nullable now) |

`message_citations` mirrors this: `ticker` / `form` / `filing_date` are
nullable and a `title` snapshot column was added, because citations of
generic documents have no SEC metadata.

## 10. Storage model / upload flow

`backend/app/storage.py` — files live under `DOCUMENT_STORAGE_DIR`
(default `backend/data/documents/`, gitignored) named
`<sha256><original-suffix>`. Consequences:

- no client-supplied path ever reaches the filesystem; original filenames
  survive only as the document title;
- identical bytes map to one file (idempotent re-store);
- `resolve_stored_path` refuses paths escaping the storage root.

`POST /documents` (backend/app/api/documents.py, multipart):

1. Supabase JWT auth (existing `get_current_user`).
2. Extension allowlist → 415; magic-byte check → 415.
3. Empty body → 422; size > `MAX_UPLOAD_SIZE_MB` (default 50) → 413.
4. Store file; register/ingest synchronously in a threadpool.
5. Content-hash dedup: identical bytes return the existing document
   (HTTP 200, `deduplicated: true`); `?force=true` re-ingests with the same
   citation-deletion semantics as the SEC `--force` CLI.
6. The document row and its chunks commit in one transaction
   (`write_chunks`); conversion/embedding failures roll the registration
   back — no half-created records.

Errors map explicitly: 415 unsupported, 422 empty/conversion/OCR/empty-text/
invalid language, 413 oversize, 409 concurrent identical registration, 500
embedding/database failures.

Language metadata (`language` form field) is validated against
`^[a-z]{2}(-[A-Za-z]{2,8})?$|^mixed$|^unknown$`; no automatic detection is
attempted — uncertain language stays NULL by design.

## 11. Normalization and search_text

Every chunk — SEC or generic — is written by `ingest.persist.write_chunks`:

```text
ChunkRecord.text (canonical, cited verbatim)  → document_chunks.text
normalize(chunk.text) (Sprint 1 canonical normalizer) → document_chunks.search_text
existing OpenAI embedding path → document_chunks.embedding
```

No duplicate normalization code exists; `document_chunks.text` is never
rewritten. Pinned by `test_write_chunks_keeps_canonical_text_and_derives_search_text`.

## 12. Chunking behavior

Unchanged: `HybridChunker`, `CHUNK_MAX_TOKENS=512`, tiktoken `cl100k_base`,
`merge_peers=True`, markdown table serialization. No semantic/hierarchical
chunking introduced. Neighbor expansion, filters, RRF, embeddings (OpenAI
`text-embedding-3-small`, 1536 dims) untouched.

## 13. Idempotency

- Generic dedup identity: `content_hash` (unique partial index, NULLs
  exempt). Re-registering identical bytes never creates duplicate documents
  or chunks.
- `skip_existing` (default): documents that already have chunks are skipped.
- `--force` / `?force=true`: deletes chunks (and citations referencing them,
  preserving the existing explicit-replace semantics of the SEC CLI) then
  re-ingests. `ON DELETE RESTRICT` protection is unchanged — citations are
  only removed by an explicit force/reindex operation.

## 14. API security constraints

- Authentication: existing Supabase JWT dependency; no new middleware.
- No path traversal: filenames are server-generated (content hash).
- Validation at the boundary: extension allowlist, magic bytes, empty and
  size checks, language validation.
- Documents are a shared corpus: the endpoint authenticates the uploader but
  `source_documents` has no user dimension and retrieval is global (same as
  SEC filings). Per-user scoping is out of scope for this sprint.
- `ensure_user` is intentionally not called: no user FK is involved.

## 15. CLI

`uv run python -m ingest.generic --file <path> [--title] [--language]
[--dry-run] [--skip-existing/--no-skip-existing] [--force] [--max-chunks N]`
copies the file into the storage root (same content-hash flow as the API)
and ingests it. Existing SEC commands are untouched:

- `uv run python -m ingest.load_source_documents`
- `uv run python -m ingest.chunk_and_embed --all | --accession <no> [--force]`

## 16. Frontend scope (minimal)

The full Persian UI/RTL/i18n sprint is later. Only the citation display
types were adjusted so citations of generic documents validate and render:

- `lib/citations.ts`: `ticker` / `form` / `filingDate` are `string | null`,
  optional `title` added; guard accepts null; labels fall back to title /
  "Document". SEC citation rendering is byte-identical to before.
- `lib/chat.ts`: `CitationContext` mirrors the backend response.
- `SourcePassageSheet.tsx`: SEC badges render only when present.

## 17. Known limitations

- OCR: no runnable engine in this environment; RapidOCR requires
  modelscope.cn access (or pre-seeded model files); Persian (`fas`) OCR
  requires tesseract with `fas` traineddata.
- `PARTIAL_SUCCESS` documents are rejected, not partially ingested.
- Generic table chunks are inline markdown inside narrative chunks;
  `document_tables` rows are written for SEC documents only (the citation
  viewer consumes `chunk_metadata`, which generic chunks carry).
- No per-user document ownership; upload is authenticated but global.
- The API ingests synchronously; large PDFs will hold the request open.
