# Sprint 5 Report — PDF / OCR / Image Readiness

## 1. Objective

Sprint 5 validates whether the multi-format document ingestion pipeline (implemented in Sprint 4) is reliable, robust, and safe for real-world production use across digital PDFs, scanned PDFs, OCR-based documents, image files, Persian documents, English documents, and mixed Persian/English documents.

The primary question addressed:
> Can this Document Copilot safely ingest real PDF/image/scanned documents and expose their content to the existing RAG + citation system without corrupting source text or silently producing bad evidence?

Strategy applied: **KEEP → TEST → HARDEN ONLY WHERE EVIDENCE JUSTIFIES IT**.

---

## 2. Current Implementation Audited

The audited architecture spans:
- `backend/ingest/formats.py`: Extension mapping and magic-byte signature validation (`%PDF-`, `PK\x03\x04`, image headers).
- `backend/ingest/generic.py`: Generic Docling conversion, OCR pipeline options wiring, section extraction, and chunking.
- `backend/ingest/chunking.py`: `HybridChunker` (512 tokens, `cl100k_base` tokenizer, `merge_peers=True`), page provenance extraction.
- `backend/ingest/persist.py`: Shared embedding, canonical text retention (`document_chunks.text`), normalized search text derivation (`document_chunks.search_text = normalize(text)`), and transactional database persistence.
- `backend/app/storage.py`: Content-hash file naming (`<sha256><suffix>`), storage path resolution, and path traversal prevention.
- `backend/app/api/documents.py`: Authenticated multipart upload endpoint `POST /documents` with deduplication and force re-ingest.
- `backend/app/schemas/documents.py`: `DocumentResponse` model.
- `backend/app/config.py`: `ocr_enabled`, `ocr_engine`, `ocr_languages`, and storage limits.

---

## 3. Readiness Matrix

| Capability | Language | Status | Evidence |
| :--- | :--- | :--- | :--- |
| Digital PDF | English | **PASS** | `test_digital_english_pdf_readiness` extracts text, preserves pages 1–3, extracts sections |
| Digital PDF | Persian | **PASS** | `test_digital_persian_pdf_readiness` extracts Persian letters, ZWNJ, digits, English terms (`OpenAI`, `AI`, `10-K`) |
| Digital PDF | Mixed | **PASS** | `test_digital_mixed_pdf_readiness` extracts mixed Persian/English (`MSFT`, `Azure`, `AI revenue`, `درآمد`) |
| Multi-column PDF | English | **PARTIAL** | `test_digital_multicolumn_pdf_assessment` extracts all text, but lines interleave horizontally across columns |
| Scanned PDF | English | **PASS** | `test_rapidocr_scanned_pdf_readiness` extracts text across pages 1 & 2 with RapidOCR |
| Scanned PDF | Persian | **NOT RUN** | Tesseract CLI binary is absent on host; RapidOCR lacks Persian models |
| Image (PNG/JPG/WEBP/TIFF/BMP) | English | **PASS** | `test_rapidocr_english_image_readiness` extracts text with RapidOCR; all format magic bytes verified |
| Image | Persian | **PARTIAL** | `test_rapidocr_persian_image_observation` confirms graceful handling, but RapidOCR produces non-Persian approximations (`'w l'`) |
| DOCX | English | **PASS** | `test_english_docx_readiness` extracts headings to sections, `page=None` |
| DOCX | Persian | **PASS** | `test_persian_docx_readiness` extracts Persian headings, ZWNJ, Persian digits, `page=None` |

---

## 4. PDF Findings

- Digital PDFs process reliably via Docling's `pypdfium2` backend and `heron` layout model.
- Canonical text layer preserves Persian letters, ZWNJ, Persian digits, Arabic-Indic digits, and English technical terms without transliteration.
- Page provenance is accurately reported for all chunks (pages 1, 2, 3).
- Headings extracted from PDF layout correctly form hierarchical section metadata (`Chapter > Section`).
- Empty or corrupted PDFs fail explicitly (`detect_format` raises `UnsupportedFormatError` on bad headers; Docling raises `ConversionError`).

---

## 5. Multi-Column Findings

- Tested with `digital-multicolumn.pdf` (two vertical columns with distinct paragraph sets).
- Docling's default layout analysis merges paragraphs horizontally line-by-line (`ALPHA-01 ... BETA-01 ... ALPHA-02 ... BETA-02`) rather than reading Column 1 completely before Column 2.
- **Decision (Part 5)**: In accordance with instructions, we do not attempt to build a custom layout engine. The limitation is reproduced, covered by a test (`test_digital_multicolumn_pdf_assessment`), and documented.

---

## 6. OCR Findings

- RapidOCR 3.8.1 is bundled and operational in this environment, with ONNX models loaded (`ch_PP-OCRv4_det_mobile.onnx`, `ch_ppocr_mobile_v2.0_cls_mobile.onnx`, `ch_PP-OCRv4_rec_mobile.onnx`).
- English OCR execution on bitmap images and scanned PDFs achieves high accuracy and high confidence scores (0.95–0.98).
- Tesseract CLI and EasyOCR are not installed on the Windows host.
- Disabling OCR (`OCR_ENABLED=False`) fails fast when an image is uploaded with `ConversionError("Image ingestion requires OCR...")`.

---

## 7. Persian OCR Findings

- RapidOCR's default recognition model catalog is limited to Chinese and Latin/English characters (`PP-OCRv4`). When presented with Persian text (`scan-persian.png`), RapidOCR transcribes it into non-Persian ASCII approximations (`'w l'`).
- Tesseract Persian OCR (`fas.traineddata`) requires the native `tesseract` binary, which is absent on this host.
- Persian OCR via Tesseract is honestly reported as **NOT RUN — tesseract binary unavailable**.
- RapidOCR's inability to recognize Persian script is documented as a known limitation.

---

## 8. Image Findings

- Direct image ingestion supports PNG, JPG/JPEG, WEBP, TIFF, and BMP formats.
- Magic-byte signatures are strictly verified (`\x89PNG`, `\xff\xd8\xff`, `BM`, `II*`, `MM*`, `RIFF`).
- Readable English images produce valid chunks when OCR is enabled.
- Blank/empty images produce zero chunks and fail cleanly without creating empty database rows.

---

## 9. Page Metadata Findings

- **PDF**: Real page provenance is populated (`"1"`, `"2"`, `"3"`) from Docling provenance.
- **DOCX**: DOCX documents have no concept of pages. `page = None` is strictly maintained and never faked.
- **Images**: Real image provenance is preserved (`page = "1"` or `None`).

---

## 10. Section Metadata Findings

- Headings are extracted from recognized Docling structure items (`SectionHeaderItem`, `TitleItem`).
- For generic documents with headings, `section` contains the hierarchy (`" > ".join(headings)`).
- Generic documents without headings receive `section = None`; no fake sections (such as SEC `Item` fallbacks) are invented.

---

## 11. Canonical Text / search_text Integrity

- `document_chunks.text` stores the canonical extracted text verbatim.
- `document_chunks.search_text = normalize(text)` derives the normalized representation for search indexing.
- Persian digits are folded to ASCII in `search_text` (`۱۴۰۳` → `1403`), while canonical text retains the original Persian digits.
- Canonical text is never overwritten by normalization.

---

## 12. Citation Readiness

- Generic document citations correctly populate `title` while leaving SEC fields (`ticker`, `form`, `filing_date`) `None`.
- `RetrievedPassage` and `CitationPayload` schemas support generic documents without validation errors.
- `TurnRegistry` allowlists generic passages based on `chunk_id`.

---

## 13. Grounding Readiness

- `GroundingValidator` validates generic document citations using the canonical chunk text (`document_chunks.text`).
- Verbatim excerpts validate successfully.
- Unreferenced citations are pruned.
- Citations referencing un-retrieved chunk IDs fail-closed with `"Citation references chunk ... that was not retrieved."`.

---

## 14. Retrieval Compatibility

- Chunks from generic documents participate in hybrid retrieval without architectural changes.
- `normalize(query)` matches `search_text`.
- `extract_fts_keywords` extracts high-value keywords (`شرکت`, `درامد`, `1403`) from queries against generic chunk texts.

---

## 15. API Readiness

- `POST /documents` endpoint enforces authentication (401 without valid JWT).
- Valid PDF and DOCX uploads return HTTP 201 with `DocumentResponse`.
- Re-uploading identical bytes returns HTTP 200 with `deduplicated: True`.
- `?force=true` triggers re-ingestion and replaces existing chunks.

---

## 16. Security Validation

- Extension allowlist and magic-byte verification reject mismatched files (HTTP 415).
- Empty uploads are rejected (HTTP 422).
- Oversized uploads exceeding `MAX_UPLOAD_SIZE_MB` are rejected (HTTP 413).
- Path traversal is prevented via SHA-256 content-hash storage paths (`app/storage.py`).

---

## 17. Idempotency / Re-ingestion

- Content-hash unique partial index prevents duplicate document rows for identical uploads.
- Default `skip_existing=True` skips chunking when chunks already exist.
- Force re-ingest deletes old chunks and referencing citations first, respecting `ON DELETE RESTRICT`.

---

## 18. Quality Gates Added

1. **Header-Only / Image Text Fallback**:
   - Prevents valid short scans, invoices, and title pages from being falsely discarded as empty documents when Docling's `HybridChunker` emits zero body chunks.
2. **Empty Scan Rejection**:
   - Rejects blank scans/images explicitly via `EmptyDocumentError` rather than indexing empty rows.
3. **Mismatched Content Rejection**:
   - Rejects files whose content signature contradicts their file extension.

---

## 19. Targeted Fixes

### Fix 1: Header-Only Content Fallback in Ingestion
- **File**: `backend/ingest/generic.py`
- **Problem**: When a document or scan contains text classified as `SectionHeaderItem` or `TitleItem` without body paragraphs, Docling's `HybridChunker` produces zero body chunks (`c.text == ""`), causing `ingest_file` to raise `EmptyDocumentError` on readable documents.
- **Fix**: Added a fallback in `chunk_generic_document`: if `records` is empty but `doc.texts` contains extracted text, group items by page and emit coherent `ChunkRecord`s.
- **Regression Test**: `tests/ingest/test_readiness_ocr_image.py::test_rapidocr_english_image_readiness` and `test_rapidocr_scanned_pdf_readiness`.

### Fix 2: Scanned PDF Fixture Generator Image Attachment
- **File**: `backend/tests/fixtures/documents/generate_fixtures.py`
- **Problem**: `pdf_scanned` called `build_pdf` without attaching the JPEG image XObject or painting operators (`/Im0 Do`) when `font` was None, generating empty PDF pages.
- **Fix**: Updated `build_pdf` to always register and draw image XObjects when `page.jpeg` is present.
- **Regression Test**: `tests/ingest/test_readiness_ocr_image.py::test_rapidocr_scanned_pdf_readiness`.

### Fix 3: Ingestion Diagnostic Reporting
- **File**: `backend/ingest/generic.py`
- **Problem**: Conversion failures did not expose format, parser, or OCR configuration diagnostics to operators.
- **Fix**: Enhanced `ConversionError` to include `[format=..., parser=docling, ocr_enabled=..., ocr_engine=..., ocr_languages=...]`.
- **Regression Test**: `tests/ingest/test_generic.py::test_convert_document_fails_explicitly`.

---

## 20. Tests Added

- `backend/tests/ingest/test_readiness_pdf.py` (3 fast tests, 4 integration tests): format detection, metadata preservation, corrupted PDF, digital English PDF, digital Persian PDF, digital mixed PDF, multi-column assessment.
- `backend/tests/ingest/test_readiness_docx.py` (2 fast tests, 2 integration tests): format detection, `page=None` invariant, English DOCX readiness, Persian DOCX readiness.
- `backend/tests/ingest/test_readiness_ocr_image.py` (10 fast tests, 4 integration tests, 1 skipped): magic-byte checks across 5 image formats, mismatched magic bytes, empty images, OCR-disabled rejection, OCR configuration validation, Tesseract status check, RapidOCR English image, RapidOCR scanned PDF, RapidOCR Persian observation, empty scan quality gate.
- `backend/tests/ingest/test_readiness_integrity.py` (6 fast tests): canonical text retention, search_text derivation, TurnRegistry registration, CitationPayload schema, GroundingValidator with generic passages, search keyword extraction.
- `backend/tests/api/test_documents_readiness.py` (8 fast tests): valid PDF upload, deduplication (200), magic-byte mismatch (415), unsupported extension (415), empty upload (422), oversize upload (413), invalid language (422), authentication check (401).

---

## 21. Test Results

Exact executed commands and outputs:

```text
focused readiness tests:       29 passed, 1 skipped, 10 deselected in 32.80s
                               (uv run pytest tests/ingest/test_readiness_pdf.py tests/ingest/test_readiness_docx.py tests/ingest/test_readiness_ocr_image.py tests/ingest/test_readiness_integrity.py tests/api/test_documents_readiness.py -m "not integration")

readiness integration tests:   10 passed, 16 deselected in 129.50s
                               (uv run pytest tests/ingest/test_readiness_pdf.py tests/ingest/test_readiness_docx.py tests/ingest/test_readiness_ocr_image.py -m "integration")

full non-integration suite:    348 passed, 15 skipped, 56 deselected in 40.44s
                               (uv run pytest -m "not integration")
                               (Sprint 4 baseline: 319 passed / 14 skipped — +29 new passing fast tests, zero regressions)

ruff:                          PASS (All checks passed!)
                               (uv run ruff check .)

OCR integration:               PASS (RapidOCR on English image and 2-page scanned PDF)
                               PARTIAL (RapidOCR evaluated on Persian image — outputs non-Persian approximations)
                               NOT RUN (Tesseract Persian OCR — tesseract binary unavailable on host)

image integration:             PASS (PNG, JPG, BMP, TIFF, WEBP format verification + real PNG OCR)

API integration:               PASS (8 focused API readiness tests in test_documents_readiness.py + 10 in test_documents.py)
```

---

## 22. Files Created

```text
backend/tests/ingest/test_readiness_pdf.py
backend/tests/ingest/test_readiness_docx.py
backend/tests/ingest/test_readiness_ocr_image.py
backend/tests/ingest/test_readiness_integrity.py
backend/tests/api/test_documents_readiness.py
docs/sprint-5-pdf-ocr-image-readiness.md
docs/sprint-5-report.md
```

---

## 23. Files Modified

```text
backend/ingest/generic.py                                (header-only chunking fallback; operator diagnostics)
backend/tests/fixtures/documents/generate_fixtures.py    (image XObject / Im0 Do paint operator fix in build_pdf)
backend/tests/fixtures/documents/pdf/scanned-english.pdf (regenerated with image XObject)
backend/tests/fixtures/documents/pdf/scanned-persian.pdf (regenerated with image XObject)
```

---

## 24. Known Limitations

1. **Persian OCR Not Executed via Tesseract**:
   - Native `tesseract` binary is not installed on the Windows host environment.
   - Recorded honestly as `NOT RUN — tesseract binary unavailable`.
2. **RapidOCR Model Catalog**:
   - RapidOCR bundles `ch_PP-OCRv4` models (Chinese and English). It does not support Persian script and outputs non-Persian character approximations on Persian scans.
3. **Multi-Column Reading Order**:
   - Docling layout model merges two-column paragraphs horizontally line-by-line when explicit visual dividers are absent.
4. **Synchronous Upload Endpoint**:
   - `POST /documents` executes conversion and embedding synchronously on the worker threadpool; large documents will hold the connection open.

---

## 25. Deferred Work

- Persian OCR engine setup (Tesseract with `fas.traineddata` or fine-tuned PaddleOCR) in a production container.
- OCR engine benchmarking across large real-world scanned corpora.
- Image preprocessing (deskewing, binarization, rotation correction).
- Advanced Persian morphology (suffix folding, stemming).
- Reranker and embedding model evaluation.
- Full Persian UI / RTL / i18n sprint.

---

## 26. Recommendation for Sprint 6

The backend document ingestion pipeline is thoroughly validated across digital PDFs, DOCX, English scans, and images. Canonical text and citation integrity are proven. However, **the user-facing product surface remains English-only and lacks an upload interface**.

Sprint 6 should focus on:
1. **Frontend Document Upload UI**: Wire an upload modal / drawer to `POST /documents` so users can ingest PDF, DOCX, and image documents from the browser.
2. **Persian UI & RTL Layout**: Implement RTL directionality (`dir="rtl"` / `dir="auto"`), Persian typography (Vazirmatn font integration), and Persian UI localization.
3. **Docker / Environment Setup for Persian OCR**: Provide a container definition bundling `tesseract` and `fas.traineddata` so Persian scanned documents can be OCR'd in production.
