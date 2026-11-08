# SPRINT 5.5 REPORT — Showcase / Evidence Mode

## 1. Implementation Summary

Sprint 5.5 establishes a polished, screenshot-ready **Showcase / Evidence Mode** inside Document Copilot. The implementation introduces a dedicated, read-only presentation surface (`/showcase`) designed specifically to produce defensible, high-resolution evidence screenshots for project documentation, portfolio, and case-study content without modifying production retrieval semantics, faking AI output, or manufacturing artificial scores.

The implementation comprises:
1. **Deterministic Demo Corpus & Real Ingestion Pipeline:** 4 multi-page digital PDFs (Persian, English, and Mixed) generated with real text layers and Vazirmatn font, and converted through the actual Docling `DocumentConverter` and `HybridChunker` pipeline.
2. **Real Conversation Analysis:** Grounded question answering executing through normalization, hybrid search (`pgvector` + FTS), RRF fusion, answer generation, and grounding validation with citations referencing canonical `document_chunks.text`.
3. **8-Step Technical Analysis Trace:** Compact status audit trail verifying every runtime step without simulated animations.
4. **30-Case Evaluation Suite & Runner:** Automated evaluation runner assessing Hit@10, grounding validity, citation correctness, and fail-closed unanswerable handling across 6 categories.
5. **Frontend Showcase Route (`/showcase`):** Persian-first, RTL (`dir="rtl"`), desktop-first presentation interface with direct scene query-param switching (`?scene=product`, `?scene=analysis`, `?scene=evaluation`).

---

## 2. Showcase Architecture

The showcase layer sits directly on top of the existing application stack:

```text
                                  /showcase Route (React SPA)
                                                │
                 ┌──────────────────────────────┼──────────────────────────────┐
                 ▼                              ▼                              ▼
          Scene 01: Product             Scene 02: Analysis             Scene 03: Eval
       (Catalog & Readiness)         (Grounded Turn & Citations)   (30-Case Dashboard)
                 │                              │                              │
                 └──────────────────────────────┼──────────────────────────────┘
                                                ▼
                                    GET /showcase/* (FastAPI)
                                                │
                 ┌──────────────────────────────┼──────────────────────────────┐
                 ▼                              ▼                              ▼
      artifacts/documents.json       artifacts/analysis.json       artifacts/evaluation.json
                 ▲                              ▲                              ▲
                 │                              │                              │
      python -m scripts.seed_showcase            │           python -m scripts.run_showcase_eval
                 │                              │                              │
                 ├── Docling DocumentConverter   └── GroundingValidator         └── 30-Case Evaluation
                 ├── HybridChunker (512 tokens)      prune_unreferenced_citations   Dataset & Metrics
                 └── Canonical text provenance       canonical chunk text           Hit@10 / Fail-Closed
```

---

## 3. Demo Corpus

Four synthetic, internally consistent PDF documents were generated under `backend/data/showcase_corpus/`:

| Document | Format | Language | Pages | Chunks | Content Domain |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `01_annual_report_fa.pdf` | PDF | Persian (`fa`) | 3 | 5 | Operating income decline analysis (-26%), revenue growth (+24%), financial table, cloud cost driver (+28%). |
| `02_financial_summary_en.pdf` | PDF | English (`en`) | 2 | 3 | Consolidated statements of operations, SaaS revenue ($25.8M), CapEx ($5.4M), GPU cluster leasing costs. |
| `03_strategy_mixed.pdf` | PDF | Mixed (`mixed`) | 2 | 2 | Cloud Native strategy, Supabase PostgreSQL, Hybrid Retrieval (RRF + pgvector), 99.95% SLA, P95 latency. |
| `04_hr_performance_fa.pdf` | PDF | Persian (`fa`) | 2 | 2 | Workforce metrics (480 employees, 62% technical), 89% talent retention rate, 12,400 training hours. |

All documents were ingested through the real Docling pipeline and chunked using `HybridChunker` (512 tokens).

---

## 4. Evaluation Dataset

The evaluation suite includes exactly 30 test cases distributed across 6 categories:

| Category | Cases | Language | Focus |
| :--- | :---: | :--- | :--- |
| **Persian factual** | 8 | Persian | Numeric financial facts, operating profit causes, headcount, retention. |
| **English factual** | 5 | English | Consolidated revenue, operating income YoY, segment SaaS revenue, CapEx. |
| **Mixed-language** | 5 | Mixed | Technical architecture terms (Supabase, PostgreSQL, RRF, SLA, P95 latency). |
| **Multi-document** | 5 | Mixed / FA | Cross-document synthesis (financial report + strategy, HR + financial). |
| **Multi-chunk reasoning** | 3 | Persian | Multi-step reasoning across non-adjacent chunks in annual report. |
| **Unanswerable / Grounding** | 4 | FA / EN | Rejection of fabricated facts (quantum encryption, Dubai branch, dividend per share). |
| **TOTAL** | **30** | — | — |

---

## 5. Evaluation Results

The evaluation runner executed all 30 test cases against real application retrieval and validation components:

```text
======================================================================
EVALUATION METRICS SUMMARY
======================================================================
Total Test Cases:               30
Passed:                         26
Failed:                          4
Pass Rate:                    86.7%

Retrieval Hit@10:            100.0%  (Target doc in top 10 for all answerable queries)
Grounding Validity:           86.7%
Citation Correctness:         84.6%
Unanswerable Rejection Rate: 100.0%  (4/4 fail-closed verifications passed)

Language Breakdown:
  Persian Queries:            88.2%  (15/17 passed)
  English Queries:           100.0%  (6/6 passed)
  Mixed Queries:              71.4%  (5/7 passed)
======================================================================
```

### Transparent Failure Accounting
1. `EVAL-001` (Persian factual): Missing required evidence keywords in top passages (`['۱۸۵', '۱۴۰۴']`) due to table digit layout segmentation in Docling.
2. `EVAL-008` (Persian factual): Missing keyword `نگه‌داشت` due to line-break space variations in text extraction.
3. `EVAL-016` (Mixed language): Missing `۳۵۰` latency keyword due to number token separation.
4. `EVAL-019` (Multi-document): Failed multi-token cross-language keyword aggregation in top passage chunk window.

---

## 6. Screenshot Scenes

Three desktop scenes are ready for high-resolution capture at 1440 × 900:

1. **Scene 01 — Product Overview (`/showcase?scene=product`):**
   - Header: `Document Copilot | تحلیل هوشمند اسناد` with `● System Ready` badge.
   - Document cards with format, language, page count, chunk count, and `Indexed ✓` badge.
   - Architecture foundation card highlighting Supabase, pgvector, and RRF.

2. **Scene 02 — Real Analysis (`/showcase?scene=analysis`):**
   - Persian user query bubble: *"بر اساس گزارش عملکرد سال ۱۴۰۴، مهم‌ترین عوامل کاهش سود عملیاتی شرکت چه بوده است؟"*
   - Grounded assistant response bubble with clickable citations `[1]`, `[2]`.
   - Side Evidence Panel displaying canonical excerpt from `document_chunks.text` (Page 1).
   - 8-Step Technical Analysis Trace with completed green checkmarks.

3. **Scene 03 — Evaluation Dashboard (`/showcase?scene=evaluation`):**
   - Hero statistics: `30 TEST CASES`, `26 PASSED`, `86.7% PASS RATE`.
   - Quality cards: `Hit@10: 100.0%`, `Grounding: 86.7%`, `Citations: 84.6%`, `Unanswerable: 100.0%`.
   - Filterable Test Cases Detail Table showing query, retrieval hit, grounding, and failure reasons.

---

## 7. Real vs Synthetic Data

| Dimension | Classification | Explanation |
| :--- | :--- | :--- |
| **Demo Documents** | Synthetic | Fictional enterprise (*شرکت فناوری پیشگامان البرز*); no private or proprietary data used. |
| **PDF Binary Files** | Real File | Actual valid PDF files generated on disk with embedded Vazirmatn font. |
| **Ingestion Pipeline** | Real Runtime | Ingested via Docling `DocumentConverter` and `HybridChunker` (512 tokens). |
| **Search Text Derivation** | Real Runtime | Canonical `chunk.text` preserved; `search_text = normalize(text)` derived. |
| **Analysis Conversation** | Real Runtime | Real Persian question answered using retrieved chunks and grounded facts. |
| **Citation Excerpts** | Real Runtime | Provenance strictly extracted from `document_chunks.text`, never `search_text`. |
| **Evaluation Metrics** | Real Measured | Computed dynamically by `run_showcase_eval`; no manufactured scores. |
| **Model Configuration** | Real Configuration | Displays configured settings (`gpt-5.5`, `text-embedding-3-small`, `gpt-4.1-mini`). |

---

## 8. Tests

A comprehensive test suite was implemented in `backend/tests/showcase/test_showcase.py`:
- `test_showcase_dataset_structure`: Verified 30 cases across 6 categories.
- `test_showcase_documents_artifact`: Verified document counts, file existence, and chunk counts.
- `test_showcase_analysis_artifact_and_citations`: Verified real answer, canonical citation provenance, and 8-step trace.
- `test_showcase_evaluation_metrics_integrity`: Verified metric bounds, total sums, and failure logging.
- `test_showcase_api_overview`: Verified `GET /showcase/overview` HTTP 200 contract.
- `test_showcase_api_analysis`: Verified `GET /showcase/analysis` HTTP 200 contract.
- `test_showcase_api_evaluation`: Verified `GET /showcase/evaluation` HTTP 200 contract.

**Result: 7 passed in 41.46s.**

---

## 9. Validation

1. **Backend Tests:** `uv run pytest tests/showcase/ -v` → **7 passed**.
2. **Backend Full Regression:** `uv run pytest -m "not integration" -q` → **All green**.
3. **Backend Lint:** `uv run ruff check .` → **All checks passed**.
4. **Showcase Seeder:** `python -m scripts.seed_showcase` → **Success**.
5. **Showcase Evaluator:** `python -m scripts.run_showcase_eval` → **Success**.
6. **Frontend Lint:** `npm run lint` (`eslint .`) → **0 errors, 0 warnings**.
7. **Frontend Build:** `npm run build` (`tsc -b && vite build`) → **Built in 6.27s**.

---

## 10. Limitations

1. **Persian Layout Table Digit Segmentation:** In PDF layout extraction, Persian digits in tightly bounded table cells may experience segment ordering inversion (`۵۸۱` instead of `۱۸۵`), which caused keyword presence check to fail in `EVAL-001`.
2. **Multi-Column PDFs:** As documented in Sprint 5, horizontal interleaving in multi-column layouts remains a known characteristic of Docling layout analysis without custom OCR post-processing.
3. **Offline Mode Embedding:** When running offline without active OpenAI API keys, the seeder and evaluator utilize deterministic normalized term representations while strictly validating RRF fusion and citation extraction.

---

## 11. Files Changed

### Backend Files
- `backend/showcase/__init__.py` [NEW]
- `backend/showcase/corpus_generator.py` [NEW]
- `backend/showcase/evaluation_dataset.py` [NEW]
- `backend/showcase/artifacts.py` [NEW]
- `backend/scripts/seed_showcase.py` [NEW]
- `backend/scripts/run_showcase_eval.py` [NEW]
- `backend/app/api/showcase.py` [NEW]
- `backend/app/main.py` [MODIFIED]
- `backend/tests/showcase/test_showcase.py` [NEW]
- `backend/.env` [NEW]

### Frontend Files
- `frontend/src/lib/showcase.ts` [NEW]
- `frontend/src/pages/showcase/types.ts` [NEW]
- `frontend/src/pages/showcase/SceneProductOverview.tsx` [NEW]
- `frontend/src/pages/showcase/SceneRealAnalysis.tsx` [NEW]
- `frontend/src/pages/showcase/SceneEvaluation.tsx` [NEW]
- `frontend/src/pages/showcase/ShowcasePage.tsx` [NEW]
- `frontend/src/App.tsx` [MODIFIED]
- `frontend/.env` [NEW]

### Documentation Files
- `docs/sprint-5.5-showcase.md` [NEW]
- `docs/sprint-5.5-report.md` [NEW]

---

## 12. Commands

```bash
# Seed showcase demo corpus and conversation
uv run python -m scripts.seed_showcase

# Run 30-case evaluation runner
uv run python -m scripts.run_showcase_eval

# Run showcase unit tests
uv run pytest tests/showcase/ -v

# Run full backend regression
uv run pytest -m "not integration" -q

# Run backend linter
uv run ruff check .

# Run frontend linter
npm run lint

# Run frontend production build
npm run build
```

---

## 13. Regression Check

- **Ingestion Pipeline:** Unmodified. SEC and generic ingestion (`ingest.chunk_and_embed`, `ingest.generic`) continue to function without changes.
- **Grounding Contract:** Maintained. `prune_unreferenced_citations` and fail-closed validation were preserved.
- **Existing Routes:** `/login`, `/signup`, `/chats`, `/chats/:threadId` remain completely functional.
- **Storage & Dedup:** Content-hash storage and format verification remain untouched.

---

## 14. Recommendation

1. **Capture Showcase Evidence:** Use standard 1440 × 900 browser window to capture Screenshots A, B, and C from `/showcase?scene=product`, `/showcase?scene=analysis`, and `/showcase?scene=evaluation`.
2. **Include in Portfolio & Case-Study Content:** Highlight the 86.7% pass rate, 100% Hit@10, and the fail-closed unanswerable query rejection as concrete evidence of AI engineering rigor.
3. **Persian Layout Post-Processing:** In future sprints, consider introducing a lightweight table digit normalizer for Persian layout text layers to elevate the pass rate from 86.7% to >93%.
