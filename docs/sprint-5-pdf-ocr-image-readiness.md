# Sprint 5 — PDF, OCR, and Image Readiness Assessment

Date: 2026-09-17
Workspace: `development` snapshot (`daveebbelaar/document-copilot`)
Status: Quality validation, format readiness assessment, and targeted hardening complete.

---

## 1. Sprint Objective

Sprint 4 implemented a multi-format document ingestion pipeline covering PDF, DOCX, generic HTML, OCR wiring, and direct image ingestion. Sprint 5 determines whether this pipeline is reliable, robust, and safe for real-world production use, specifically answering:

> Can this Document Copilot safely ingest real PDF, image, and scanned documents and expose their content to the existing RAG + citation system without corrupting source text or silently producing bad evidence?

The strategy followed: **KEEP → TEST → HARDEN ONLY WHERE EVIDENCE JUSTIFIES IT**.

---

## 2. Current PDF Architecture

Digital PDFs flow through the generic Docling pipeline (`backend/ingest/generic.py`):
1. **Format Detection & Verification**: `backend/ingest/formats.py` validates `.pdf` extension and verifies magic bytes (`%PDF-`).
2. **Parser**: Docling `DocumentConverter` with `InputFormat.PDF` and `PdfPipelineOptions(do_ocr=settings.ocr_enabled)`. The underlying PDF engine uses `pypdfium2` for digital text layer extraction and the `heron` layout model for document structure.
3. **Chunking**: Converted `DoclingDocument` is processed by `chunk_generic_document`, reusing `HybridChunker` (`CHUNK_MAX_TOKENS=512`, `cl100k_base` tokenizer, `merge_peers=True`).
4. **Page & Section Provenance**: Page provenance is extracted via `page_from_chunk_meta` (`item.prov[].page_no`), and section hierarchy is derived via `section_from_headings` (`" > ".join(meta.headings)`).
5. **Persistence**: Chunks are written via `ingest.persist.write_chunks`: `document_chunks.text` stores canonical extracted text, `document_chunks.search_text = normalize(text)` stores the normalized representation, and embeddings (1536-dim OpenAI `text-embedding-3-small`) are generated in batches.
6. **Error Handling**: `PARTIAL_SUCCESS` and parser exceptions raise `ConversionError`. Empty extractions raise `EmptyDocumentError`.

---

## 3. Current OCR Architecture

OCR is configurable via `backend/app/config.py`:
- `OCR_ENABLED`: boolean flag (default `False`). Gates OCR execution for PDF and image pipelines.
- `OCR_ENGINE`: selects OCR backend. Supported values: `rapidocr`, `tesseract_cli`, `tesseract`, `easyocr`.
- `OCR_LANGUAGES`: comma-separated string (e.g. `eng` or `fas,eng`).

When `OCR_ENABLED=True`:
- `build_converter` sets `PdfPipelineOptions.do_ocr=True` and constructs engine options with `lang=settings.ocr_language_list`.
- For image formats (`InputFormat.IMAGE`), `PdfPipelineOptions` is used by Docling's `ImageFormatOption`.
- When `OCR_ENABLED=False`, converting an image raises `ConversionError("Image ingestion requires OCR...")` immediately before calling Docling.

---

## 4. Current Image Architecture

Direct image ingestion accepts PNG, JPG/JPEG, WEBP, TIFF, and BMP:
1. `detect_format` checks file magic bytes (`\x89PNG\r\n\x1a\n`, `\xff\xd8\xff`, `BM`, `II*\x00`, `MM\x00*`, `RIFF`).
2. Conversion is handled by Docling's `ImageFormatOption` with OCR enabled.
3. Chunks are generated via `chunk_generic_document` and persisted to `document_chunks`.
4. Original uploaded images are safely named by their SHA-256 content hash in `DOCUMENT_STORAGE_DIR`.

---

## 5. Supported Formats

| Format | Extension(s) | Magic Signature | Status | Parser | OCR | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| SEC HTML | `.htm`, `.html` | Manifest accession | Supported | Docling + `sec_tables` | No | Manifest-driven; regression tested |
| Generic HTML | `.html`, `.htm`, `.xhtml` | Extension authoritative | Supported | Docling default | No | Integration tested |
| Digital PDF | `.pdf` | `%PDF-` | Supported | Docling PDF | Optional | Validated on English, Persian, Mixed |
| Scanned PDF | `.pdf` | `%PDF-` | Supported | Docling PDF + OCR | Required | Validated with RapidOCR for English |
| DOCX | `.docx`, `.docm`, `.dotx` | `PK\x03\x04` | Supported | Docling MS Word | No | Validated on English and Persian |
| PNG | `.png` | `\x89PNG\r\n\x1a\n` | Supported | Docling Image + OCR | Required | Validated with RapidOCR for English |
| JPEG | `.jpg`, `.jpeg` | `\xff\xd8\xff` | Supported | Docling Image + OCR | Required | Format & magic bytes validated |
| BMP | `.bmp` | `BM` | Supported | Docling Image + OCR | Required | Format & magic bytes validated |
| TIFF | `.tif`, `.tiff` | `II*\x00` / `MM\x00*` | Supported | Docling Image + OCR | Required | Format & magic bytes validated |
| WEBP | `.webp` | `RIFF` | Supported | Docling Image + OCR | Required | Format & magic bytes validated |

---

## 6. OCR Engines & Environment Configuration

| Engine | Config Key | Availability in Environment | Supported Languages | Actual Observed Quality |
| :--- | :--- | :--- | :--- | :--- |
| **RapidOCR** | `rapidocr` | Installed (`rapidocr 3.8.1`, ONNX models cached) | Chinese, English (`PP-OCRv4`) | English: high accuracy (confidence 0.95–0.98). Persian: outputs non-Persian gibberish (`'w l'`). |
| **Tesseract CLI** | `tesseract_cli` | NOT INSTALLED (`tesseract` binary absent) | Dependent on `.traineddata` | **NOT RUN** — binary unavailable on host. |
| **EasyOCR** | `easyocr` | NOT INSTALLED (`docling[easyocr]` absent) | 80+ languages | **NOT RUN** — package not installed. |
| **PyTesseract** | `tesseract` | NOT INSTALLED (`tesseract` binary absent) | Dependent on `.traineddata` | **NOT RUN** — binary unavailable on host. |

---

## 7. Test Fixture Strategy

Fixtures are maintained in `backend/tests/fixtures/documents/` and generated by `generate_fixtures.py`:
- `pdf/digital-english.pdf`: 3-page digital PDF with distinct headings, financial text, and risk factor paragraphs.
- `pdf/digital-persian.pdf`: 2-page digital PDF with embedded Vazirmatn font subset, ToUnicode CMap, Persian headings, Persian digits (۱۴۰۳), Arabic-Indic digits (١٤٠٢), ZWNJ, and English technical terms (`OpenAI`, `AI`, `10-K`, `2024`).
- `pdf/digital-mixed.pdf`: 1-page digital PDF with mixed English identifiers (`MSFT`, `Azure`, `AI revenue`, `market competition`) and Persian narrative.
- `pdf/digital-multicolumn.pdf`: 1-page 2-column layout testing reading order and column interleaving.
- `pdf/scanned-english.pdf`: 2-page bitmap image PDF containing invoice and revenue text.
- `pdf/scanned-persian.pdf`: 1-page bitmap image PDF containing Persian financial text.
- `docx/english.docx`: Word document with Heading1 styles (`Annual Report`, `Financial Position`) and body paragraphs.
- `docx/persian.docx`: Word document with Heading1 styles (`گزارش سالانه`, `ریسک‌های بازار`), ZWNJ, and body paragraphs.
- `images/scan-english.*`: Clean scans in PNG, JPG, BMP, TIFF, and WEBP formats.
- `images/scan-persian.png`: Clean scan containing Persian text.

---

## 8. Persian OCR Findings

1. **RapidOCR Evaluation**:
   - RapidOCR 3.8.1 was evaluated on `scan-persian.png` ("گزارش مالی سال ۱۴۰۳").
   - The bundled recognition model (`ch_PP-OCRv4_rec_mobile.onnx`) contains glyphs for Chinese and basic Latin/digits only.
   - It transcribed the Persian text as `'w l'`.
   - **Conclusion**: RapidOCR cannot be used for Persian OCR without custom Persian recognition models.
2. **Tesseract Evaluation**:
   - Tesseract with `fas.traineddata` is the standard pipeline for Persian OCR.
   - The host environment lacks the native `tesseract` executable.
   - **Conclusion**: Persian OCR via Tesseract is recorded as **NOT RUN — tesseract binary unavailable**.

---

## 9. English OCR Findings

- RapidOCR executed cleanly against `scan-english.png` and `scanned-english.pdf`.
- Text extracted from `scan-english.png`: `"QUARTERLY REVENUE REPORT TOTAL 3400 UNITS SOLD\n\nRISKFACTORS REVIEWED"`.
- Text extracted from `scanned-english.pdf`: Page 1: `"INVOICE TOTAL 1250 DOLLARS DUE DATE 2024-05-30 ACCOUNT RISK REVIEW"`; Page 2: `"FISCALYEAR2024REPORT REVENUEGREWTWELVEPERCENT"`.
- Word detection boxes and confidence scores (0.95–0.98) were confirmed via raw engine probe.

---

## 10. Mixed-Language Findings

- Digital mixed documents (`digital-mixed.pdf`, `persian.docx`) preserve English technical terms (`OpenAI`, `AI`, `10-K`, `Azure`, `MSFT`) alongside Persian text without transliteration or character corruption.
- Search text normalization successfully maps Persian characters and digits while leaving English technical terms untouched.

---

## 11. Multi-Column Layout Findings

- `digital-multicolumn.pdf` features two distinct vertical columns: Column A (`ALPHA-01` through `ALPHA-05`) and Column B (`BETA-01` through `BETA-05`).
- In Docling's layout analysis, text across the two columns was merged horizontally line-by-line (`ALPHA-01 ... BETA-01 ... ALPHA-02 ... BETA-02`).
- **Policy Decision (Part 5)**: We do not attempt to build a custom layout engine. The limitation is reproduced, tested, and documented.

---

## 12. Page & Section Metadata Findings

- **PDF**: Page provenance is accurately reported from Docling's `doc_items[].prov[].page_no` (e.g. `"1"`, `"2"`, `"3"`).
- **DOCX**: DOCX files have no native page concept. The pipeline strictly sets `page = None`, never inventing page numbers.
- **Images**: Single-image documents associate with their native image representation (`page = "1"` from OCR provenance or `page = None` when unavailable).
- **Sections**: Extracted strictly from recognized headings (`section_from_headings`). For generic documents without headings, `section = None`.

---

## 13. Citation & Grounding Findings

- Non-SEC documents carry `title` (and optional/nullable SEC fields `ticker=None`, `form=None`).
- `RetrievedPassage` and `CitationPayload` correctly support `title` and nullable SEC fields.
- `TurnRegistry` allowlists generic passages without requiring SEC metadata.
- `GroundingValidator` validates citations against canonical chunk text (`document_chunks.text`).
- Unreferenced citations are pruned; citations referencing un-retrieved chunks fail-closed.

---

## 14. Search Compatibility

- Ingestion derives `search_text = normalize(chunk.text)` in `persist.py:write_chunks`.
- Persian digits are folded to ASCII in `search_text` (`۱۴۰۳` → `1403`), enabling exact search matching while keeping canonical `text` intact.
- Deterministic Persian keyword extraction (`extract_fts_keywords`) extracts high-value keywords (`شرکت`, `درامد`, `1403`) from queries against generic chunk content.

---

## 15. Security & Validation Findings

- Extension allowlist and magic-byte signature matching in `formats.py` reject fake files (e.g. `fake.pdf` containing PNG bytes or `.png` containing ASCII text).
- `app/storage.py` names files using SHA-256 content hashes, preventing directory traversal and file overwrite attacks.
- Upload API enforces file size limit (`MAX_UPLOAD_SIZE_MB`, default 50 MB) and rejects empty uploads with HTTP 422.

---

## 16. Idempotency & Re-ingestion Findings

- Content-hash indexing ensures re-uploading an identical file returns HTTP 200 with `deduplicated: True` and creates no duplicate rows or chunks.
- `?force=true` deletes old chunks and citations referencing them, safely re-ingesting without leaving orphaned records.

---

## 17. Quality-Gate Decisions & Targeted Hardening

1. **Header-Only / Scan Chunking Fallback**:
   - *Problem*: Docling's `HybridChunker` attaches headings to subsequent paragraphs. If an image or short scan consists entirely of headers/titles (common with large fonts in invoices, slides, receipts), `HybridChunker` emitted 0 body chunks, triggering `EmptyDocumentError`.
   - *Fix*: In `ingest/generic.py:chunk_generic_document`, if `HybridChunker` yields 0 chunks but `doc.texts` contains extracted text, a fallback synthesizes `ChunkRecord`s grouped by page so valid readable content is preserved.
2. **Scanned PDF Fixture Generator**:
   - *Problem*: In `generate_fixtures.py`, `pdf_scanned` did not attach the image XObject or drawing operators to the content stream when `font is None`.
   - *Fix*: Corrected `build_pdf` to always register and paint the image XObject `/Im0 Do`.

---

## 18. Known Limitations

1. **Tesseract Binary Absent**: Tesseract CLI is not installed on the Windows host. Persian OCR via Tesseract is `NOT RUN`.
2. **RapidOCR Script Catalog**: RapidOCR models lack Persian/Arabic support and output non-Persian approximations on Persian scans.
3. **Multi-Column Layout**: Docling's default layout analysis horizontally interleaves multi-column text lacking clear layout dividers.
4. **Synchronous Upload**: Document processing occurs synchronously on the worker thread pool; very large documents hold the HTTP connection.

---

## 19. Deferred Work

- Installation and benchmarking of Tesseract with `fas.traineddata` in a Linux container or production environment.
- Advanced Persian OCR engine evaluation (PaddleOCR Persian models or fine-tuned OCR).
- Multi-column layout heuristics / custom column boundary detection if Docling upstream does not resolve horizontal interleaving.
- Async background ingestion queue with job status tracking for large document batches.
