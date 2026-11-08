# Sprint 4 Report — Persian Document Ingestion

## 1. Objective

Extend the ingestion system from SEC-HTML-only into a multi-format pipeline
(PDF, DOCX, generic HTML, scanned/OCR, image) while preserving the existing
SEC ingestion, chunking, embeddings (OpenAI, 1536 dims), search_text
behavior, citation/grounding contracts, retrieval and agent architecture.

## 2. What Was Implemented

- Format dispatcher (`backend/ingest/formats.py`) with extension mapping and
  magic-byte verification.
- Generic Docling ingestion path (`backend/ingest/generic.py`) reusing the
  existing HybridChunker and the extracted shared persistence module
  (`backend/ingest/persist.py`).
- PDF, DOCX, generic HTML, and image ingestion; configurable OCR wiring
  (`OCR_ENABLED`, `OCR_ENGINE`, `OCR_LANGUAGES`).
- Schema extension for generic documents (one Alembic migration) — nullable
  SEC columns, `source_format`/`title`/`language`/`file_path`/`content_hash`,
  matching nullable citation display metadata.
- Local content-hash file storage (`backend/app/storage.py`) and the
  authenticated upload endpoint `POST /documents`
  (`backend/app/api/documents.py`).
- Operator CLI `python -m ingest.generic`.
- Citation plumbing extended for generic documents (`title` snapshot,
  nullable SEC display fields) across retrieval/agent/chat schemas.
- Minimal frontend citation-type adjustments (optional fields + conditional
  badges); no RTL, no i18n, no UI redesign.
- 5 new backend test modules + 3 fixtures; docs (this file and
  `docs/sprint-4-document-ingestion.md`).

## 3. Supported Formats

| Format       | Status | Parser | OCR | Notes |
| ------------ | ------ | ------ | --- | ----- |
| SEC HTML     | Supported (unchanged) | existing `chunking.chunk_document` + `sec_tables` | n/a | manifest-driven; regression-tested |
| Generic HTML | Supported | Docling `DocumentConverter` | n/a | integration-tested on fixture |
| PDF          | Supported (digital) | Docling PDF pipeline (pypdfium2 + heron layout model) | optional | page provenance preserved; `PARTIAL_SUCCESS` rejected |
| DOCX         | Supported | Docling MS Word backend | optional | `page=None` (never faked) |
| Scanned PDF  | Implemented, engine-dependent | Docling PDF pipeline + OCR options | required | requires `OCR_ENABLED=true` + runnable engine; NOT RUN in this environment |
| Image        | Implemented (OCR required) | Docling image pipeline (`InputFormat.IMAGE`) | required | rejected explicitly when OCR disabled |

## 4. Format Dispatcher

`backend/ingest/formats.py`. `format_for_suffix` maps extensions
(pdf/docx/docm/dotx/html/htm/xhtml/jpg/jpeg/png/tif/tiff/bmp/webp);
`detect_format` additionally verifies magic bytes (PDF `%PDF-`, DOCX zip
`PK\x03\x04`, image signatures) and raises `UnsupportedFormatError` on
mismatch or empty files. HTML has no reliable signature — extension is
authoritative there. SEC files bypass the dispatcher entirely (manifest by
accession). SEC and generic ingestion remain separate strategies.

## 5. PDF Ingestion

Digital PDF: Docling PDF backend extracts text; the existing HybridChunker
chunks it; `page` is real Docling provenance (verified `"1"` for the
single-page fixture); headings (layout model) drive `section`. Tables stay
inline markdown (existing serializer); `sec_tables` is not applied. Original
extracted text is canonical. `PARTIAL_SUCCESS` aborts ingestion with the
per-page errors listed (strict: no silently incomplete documents).

## 6. DOCX Ingestion

Docling MS Word backend through the same chunker. Paragraphs, headings,
lists, and tables flow through unchanged chunking; `page` is always `None`;
`section` comes only from recognized heading styles (fixture headings were
not recognized by the minimal fixture — `section=None`, nothing faked).

## 7. OCR Implementation

- `OCR_ENABLED` (default false) gates OCR; when enabled,
  `build_converter` sets `PdfPipelineOptions.do_ocr=true` and the engine's
  options with `lang=settings.ocr_language_list`.
- `OCR_ENGINE`: `rapidocr` (default, ships in this lockfile), `tesseract_cli`
  (system binary), `easyocr` (`docling[easyocr]` extra), `tesseract`
  (pytesseract). Unknown values fail fast.
- `OCR_LANGUAGES` comma-separated (`eng`; `fas,eng` for tesseract; rapidocr
  uses language families like `ch`/`en`). Not hard-coded to any language.
- Engine/model availability is validated at conversion time; OCR failures
  surface as explicit `ConversionError`s (mapped to HTTP 422 on the API).
- Persian-specific: `fas` requires a tesseract engine with Persian
  traineddata; RapidOCR (the engine bundled in this venv) has no Persian
  recognition model in its default catalog.

## 8. Image Ingestion

Implemented. Docling 2.96 cleanly supports direct image input
(`InputFormat.IMAGE` with jpg/jpeg/png/tif/tiff/bmp/webp), so images go
through the same converter + chunker with no new dependency. Because
docling's image pipeline reads text via OCR only, image ingestion without
OCR fails fast with an explicit message (verified by unit test).

## 9. Metadata Changes

- `source_documents`: added `source_format` (NOT NULL, server default
  `sec_html`), `title`, `language`, `file_path`, `content_hash`; made
  `ticker`, `cik`, `form`, `filing_date`, `accession_number`,
  `primary_document`, `source_url` nullable. Existing SEC rows keep working
  unchanged (verified: `source_format` defaults to `sec_html`).
- `message_citations`: added `title`; made `ticker`, `form`, `filing_date`
  nullable (snapshot metadata for generic-document citations).
- Generic documents never carry fake SEC metadata (unit-pinned:
  `ticker/accession_number are None`).
- Language field: user-provided, validated (`fa`, `en`, ISO 639-1,
  `mixed`, `unknown`), nullable/unknown when uncertain; no automatic
  detection.

## 10. Storage / Upload Flow

`POST /documents` (multipart, authenticated): extension allowlist → magic
bytes → empty check → size limit (`MAX_UPLOAD_SIZE_MB`, default 50) →
store under `DOCUMENT_STORAGE_DIR` as `<sha256><suffix>` (server-controlled
name; original filename preserved as title metadata; `resolve_stored_path`
refuses path escapes) → synchronous ingestion in a threadpool → response
with `sourceFormat`, `chunksWritten`, `deduplicated`, `createdAt`.
Content-hash dedup returns the existing document (HTTP 200) for identical
bytes; `?force=true` re-ingests. Document row + chunks commit in a single
transaction; failures roll the registration back.

## 11. Normalization and search_text

`document_chunks.text` remains the canonical source text (cited verbatim,
never rewritten). `document_chunks.search_text = normalize(text)` via the
Sprint 1 canonical normalizer, applied for every format (HTML, PDF, DOCX,
OCR output) in the single shared write path. No normalization code is
duplicated. Pinned by a unit test using Persian text (digits, ZWNJ, bidi).

## 12. Chunking and Metadata Preservation

Existing chunking remains the default and unchanged: `HybridChunker`,
`CHUNK_MAX_TOKENS=512`, tiktoken `cl100k_base`, `merge_peers`, markdown
table serialization. Page metadata preserved when available (PDF provenance;
`None` for DOCX/HTML — never invented). Section metadata: Docling heading
hierarchy for generic documents (`None` without headings); SEC `Item`
fallback untouched for SEC documents. SEC table extraction intact
(`sec_tables.py` untouched; its tests pass unmodified).

## 13. Embedding Compatibility

Confirmed: `text-embedding-3-small / 1536 dimensions unchanged`. No new
embedding model, no reindexing; new chunks use the existing
`ingest.embeddings.embed_texts` path unchanged.

## 14. SEC Regression Protection

- SEC ingestion code paths (`chunk_and_embed.ingest_document`,
  `chunk_document`, `sec_tables`) keep their behavior; the only changes are
  mechanical (persistence extracted to `ingest/persist.py`, `filing_date`
  isoformat guarded for the now-optional column).
- Existing test modules run unmodified except
  `tests/ingest/test_chunk_and_embed.py` import paths (helpers moved to
  `ingest/persist.py`).
- Full non-integration suite: 319 passed / 14 skipped — the Sprint 3
  baseline was 260 / 14, so every pre-existing test still passes.

## 15. Idempotency / Re-ingestion

- Content hash (SHA-256, unique partial index) is the deterministic dedup
  identity; repeated ingestion of the same source returns the existing
  document without duplicate chunks (unit-tested).
- `skip_existing` skips documents that already have chunks (both pipelines).
- `--force` / `?force=true` deletes citations→chunks→tables first (existing
  explicit-replace semantics); `ON DELETE RESTRICT` citation protection is
  unchanged and citations are never removed implicitly.

## 16. Security Validation

- Authenticated user required (existing Supabase JWT dependency; 401
  verified by test).
- Extension allowlist + magic-byte check (415), empty upload rejected (422),
  size limit (413), language validation (422).
- No client paths: server generates content-hash filenames; traversal
  attempt via stored paths rejected (`resolve_stored_path` unit test).
- No unnecessary middleware; existing CORS/auth conventions only.

## 17. Database Migration

- File: `backend/alembic/versions/e9f2b3c8d4a1_add_generic_document_metadata.py`
- Revision: `e9f2b3c8d4a1`, down_revision: `b8e3d5a1f4c2`
- Schema changes:
  - `source_documents`: + `source_format VARCHAR(32) NOT NULL DEFAULT 'sec_html'`,
    + `title VARCHAR(255)`, + `language VARCHAR(16)`, + `file_path TEXT`,
    + `content_hash VARCHAR(64)`, unique partial index
    `uq_source_documents_content_hash ON (content_hash) WHERE content_hash IS NOT NULL`,
    SEC identity columns → nullable.
  - `message_citations`: + `title VARCHAR(255)`;
    `ticker`/`form`/`filing_date` → nullable.
- Validation (throwaway PostgreSQL 16.14, trust-auth temp instance on port
  5433, old-shape replica of the two affected tables, stamped
  `b8e3d5a1f4c2`, deleted afterwards — the full chain from scratch needs the
  pgvector extension, which is not installed in the local distribution):
  - upgrade `b8e3d5a1f4c2 → e9f2b3c8d4a1`: PASS (columns/nullability/default
    and partial unique index verified; SEC row preserved with
    `source_format='sec_html'`).
  - generic row with NULL SEC metadata: PASS; generic citation row: PASS.
  - duplicate `content_hash` insert: rejected by the unique index (PASS).
  - downgrade `e9f2b3c8d4a1 → b8e3d5a1f4c2` after deleting the generic rows:
    PASS (SEC row and data intact); re-upgrade: PASS (round trip).
  - Downgrade with generic rows present fails by design restoring NOT NULL —
    documented in the migration docstring.

## 18. Tests Added

- `backend/tests/ingest/test_formats.py` — extension mapping, unsupported
  extensions, magic-byte mismatch, empty file, fixtures.
- `backend/tests/ingest/test_generic.py` — language validation, heading
  sections, converter OCR wiring (disabled default, engine+languages, unknown
  engine), image-without-OCR rejection, `ingest_file` (registration, title
  default, content-hash dedup, force re-ingest, empty-document failure,
  conversion failure propagation, dry run, invalid language), canonical
  text/search_text normalization pin.
- `backend/tests/ingest/test_storage.py` — hash naming, idempotent store,
  distinct content, root resolution, traversal rejection.
- `backend/tests/ingest/test_generic_integration.py` (integration-marked) —
  real conversion of bundled fixtures: digital PDF (text + page provenance),
  DOCX (text, no fake pages), generic HTML, corrupted-PDF explicit failure,
  OCR placeholder skip.
- `backend/tests/api/test_documents.py` — auth required, 415 extension,
  415 magic mismatch, 422 empty, 413 oversize, 422 invalid language, 201
  success payload, 200 deduplicated, 422 conversion/empty-document errors.
- Fixtures: `tests/fixtures/sample.pdf` (single-page digital PDF),
  `sample.docx` (minimal DOCX), `sample.png` (image).

## 19. Test Results

All commands run from `backend/` with the five required env vars as
placeholders (Sprint 0 finding K2; no `.env` created). No results invented.

```text
Focused ingestion+API tests   uv run pytest tests/ingest tests/api -m "not integration"
                              → 75 passed, 6 deselected

Full non-integration suite    uv run pytest -m "not integration"
                              → 319 passed, 14 skipped, 46 deselected
                              (Sprint 3 baseline: 260 passed, 14 skipped, 40 deselected —
                               +59 new passing fast tests, zero regressions)

Integration (real Docling)    uv run pytest tests/ingest/test_generic_integration.py
                              → 5 passed, 1 skipped (OCR placeholder)
                              Layout model was pre-cached from HuggingFace; tests are
                              integration-marked so the ordinary suite hits no network.

ruff                          uv run ruff check . → PASS (All checks passed!)

Migration validation          PASS — throwaway PostgreSQL 16.14 replica, real
                              alembic upgrade/downgrade/upgrade round trip
                              (see §17 for scope note re: pgvector)

OCR integration               NOT RUN — no runnable OCR engine in this environment:
                              RapidOCR model host (modelscope.cn) unreachable,
                              no tesseract binary, easyocr not installed. Path is
                              unit-tested (options wiring + explicit failures); real
                              OCR remains a TODO for an environment with a working engine.

OpenAI/Supabase integration   NOT RUN — no live credentials (as in Sprints 0–3).
```

Manual smoke (this environment, no external services beyond the HF-cached
layout model):

```text
uv run python -m ingest.generic --file tests/fixtures/sample.pdf --title "Sample Document Title" --language en --dry-run
→ stored as <sha256>.pdf; 1 chunk(s), max_tokens=39;
  sample page='1' section='Sample Document Title'; dry run: nothing written
uv run python -m ingest.generic --file tests/fixtures/sample.docx --dry-run
→ 1 chunk(s), max_tokens=41; sample page=None section=None
```

## 20. Files Created

```text
backend/ingest/formats.py
backend/ingest/persist.py
backend/ingest/generic.py                      (library + CLI)
backend/app/storage.py
backend/app/api/documents.py
backend/app/schemas/documents.py
backend/alembic/versions/e9f2b3c8d4a1_add_generic_document_metadata.py
backend/tests/ingest/test_formats.py
backend/tests/ingest/test_generic.py
backend/tests/ingest/test_storage.py
backend/tests/ingest/test_generic_integration.py
backend/tests/api/test_documents.py
backend/tests/fixtures/sample.pdf
backend/tests/fixtures/sample.docx
backend/tests/fixtures/sample.png
docs/sprint-4-document-ingestion.md
docs/sprint-4-report.md
```

## 21. Files Modified

```text
backend/ingest/chunk_and_embed.py        (persistence extracted to ingest/persist.py; filing_date guard)
backend/ingest/chunking.py               (_page_from_chunk_meta → public page_from_chunk_meta)
backend/app/config.py                    (+ document_storage_dir, max_upload_size_mb, ocr_enabled, ocr_engine, ocr_languages)
backend/.env.example                     (+ document storage / upload size / OCR sections)
backend/app/database/models/source_document.py   (generic metadata columns, nullable SEC fields, partial unique index)
backend/app/database/models/message_citation.py  (title column, nullable SEC display fields)
backend/app/retrieval/types.py           (RetrievedPassage: title + optional SEC fields; header formatting)
backend/app/retrieval/retriever.py       (_passage_from_chunk: + title)
backend/app/assistant/tools.py           (_passage_from_chunk: + title)
backend/app/schemas/chat.py              (CitationPayload / CitationContextResponse: optional SEC fields + title)
backend/app/chat/messages.py             (citation payload: + title)
backend/app/database/chats.py            (citation rows: title, nullable handling)
backend/app/api/chat.py                  (citation context response: + title)
backend/app/main.py                      (documents router registered)
backend/tests/ingest/test_chunk_and_embed.py     (imports after persistence extraction)
frontend/src/lib/citations.ts            (nullable SEC fields, optional title, guard + label fallbacks)
frontend/src/lib/chat.ts                 (CitationContext type mirrors backend)
frontend/src/components/chat/SourcePassageSheet.tsx  (conditional SEC badges, title fallback)
.gitignore                               (+ /data/documents/*)
```

Why these extend beyond Part 33's expected list: citation display metadata
must survive end-to-end for generic documents (schemas, chats, frontend
types); `.gitignore` protects the new storage payload directory.

## 22. Known Limitations

- **OCR is not executable in this environment.** The engine bundled in the
  venv (RapidOCR 3.8.1) downloads models from modelscope.cn, which is
  unreachable here; tesseract is not installed; easyocr is not installed.
  The OCR code path is implemented and configurable, validated by unit
  tests (wiring + explicit failures), but no real OCR run happened — no OCR
  quality claims are made. Observed: docling's default OCR auto-selection
  initializes RapidOCR even for plain `DocumentConverter()` use, and a
  modelscope outage blocks that init (our pipeline avoids this by defaulting
  `do_ocr=False`).
- Persian OCR (`fas`) specifically requires tesseract with Persian
  traineddata; RapidOCR's catalog has no Persian model.
- Image ingestion requires OCR by design; without OCR it fails fast with an
  explicit message (verified).
- `PARTIAL_SUCCESS` PDFs are rejected whole (strict completeness over
  availability).
- Generic table content stays inline markdown in narrative chunks;
  `document_tables` rows are written only for SEC documents.
- Documents are a global corpus: uploads are authenticated but not
  user-scoped.
- Synchronous API ingestion: large PDFs hold the HTTP request open.
- No live end-to-end validation against real Supabase/OpenAI (no
  credentials, as in all prior sprints).

## 23. Deferred Work

- Advanced Persian OCR quality (engine selection, `fas` traineddata setup,
  preprocessing for Persian scans).
- OCR engine benchmarking beyond minimal validation.
- Persian morphology (suffix folding, stemming).
- Persian UI / RTL / full i18n (recommended next).
- Reranker and embedding evaluation.
- Per-user document ownership / access control on the shared corpus.
- Async ingestion jobs if document volume outgrows synchronous upload.

## 24. Recommendation for Sprint 5

Based on actual results: **the backend contract for Persian content is now
complete (normalization, retrieval, LLM layer, ingestion), but the product
surface is still English-only.** Sprint 5 should deliver the Persian
frontend: RTL layout, full i18n of chat/status/citation surfaces, and a
minimal upload UI wired to `POST /documents` (the endpoint exists, is
authenticated, and returns generic-document citation payloads the UI already
accepts). This is also the sprint the user's briefs repeatedly deferred
("full Persian UI/RTL/i18n sprint is later"). Prerequisite for real value:
run the app against live credentials/corpus to validate Sprints 2–4
end-to-end — every sprint so far is validated only by tests and local
smokes. If OCR is needed before the UI sprint, set up tesseract with
`fas` traineddata first (small, well-defined prerequisite task).
