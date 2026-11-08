# Document Copilot — Showcase / Evidence Mode Guide (Sprint 5.5)

## 1. Overview & Objective

**Showcase / Evidence Mode** provides a polished, screenshot-ready presentation layer inside the Document Copilot application. It is designed to capture professional evidence screenshots for project documentation, portfolio, and case-study presentations without modifying the core product architecture, faking application behavior, or corrupting grounding contracts.

The screenshots visually communicate:
1. The application is a working document-analysis product.
2. Real questions can be answered from indexed documents.
3. Retrieval + LLM + grounding + citations are working together.
4. The system has been evaluated with a meaningful test set (30 cases).
5. Persian, English, and mixed-language documents participate in the workflow.

---

## 2. Architecture & Design Principles

### Non-Negotiable Rules Followed
- **KEEP → EXTEND → REFACTOR → REPLACE only when necessary.**
- No local LLM or BGE-M3 replacements were introduced; existing OpenAI and Supabase configurations remain authoritative.
- Retrieval semantics (`normalize` → Hybrid Search `pgvector` + FTS → RRF Fusion) were not modified or bypassed.
- Grounding and citation validation remain strictly **fail-closed**.
- Displayed citation excerpts come exclusively from `document_chunks.text`, never `search_text`.
- Evaluation scores and metrics are calculated dynamically by a real evaluation runner; no fake or hardcoded percentages.

### Route & Navigation
- **Route:** `/showcase` (supports direct scene linking via `?scene=product`, `?scene=analysis`, `?scene=evaluation`).
- **Access:** Read-only from the user perspective, isolated from normal chat navigation, no login redirect required to view showcase scenes.
- **Localization:** Persian-first, RTL (`dir="rtl"`). Technical product and architecture names remain in English (`Document Copilot`, `OpenAI`, `Supabase`, `pgvector`, `RRF`, `Python`, `FastAPI`, `PydanticAI`, `PDF`, `OCR`).

```text
SHOWCASE
├── 01 محصول      (/showcase?scene=product)
├── 02 تحلیل واقعی  (/showcase?scene=analysis)
└── 03 Evaluation (/showcase?scene=evaluation)
```

---

## 3. Demo Corpus Specification

A deterministic synthetic corpus of 4 documents was constructed under `data/showcase_corpus/`. The documents contain internally consistent business, financial, technical, and human resource information for a fictional enterprise: **شرکت فناوری پیشگامان البرز (سهامی عام) / Alborz Pioneer Technologies Inc.**

| Filename | Document Title | Language | Format | Pages | Chunks | Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `01_annual_report_fa.pdf` | گزارش عملکرد سالانه ۱۴۰۴ | Persian (`fa`) | PDF | 3 | 5 | Financial and operational summary, operating income drivers, segment results, risk management. |
| `02_financial_summary_en.pdf` | Alborz Pioneer Tech - Financial Summary 2025 | English (`en`) | PDF | 2 | 3 | Consolidated statements of operations, revenue ($42.5M), operating margin, SaaS metrics, and CapEx. |
| `03_strategy_mixed.pdf` | گزارش استراتژی و تحول دیجیتال — Strategy & Digital Transformation 2025-2026 | Mixed (`mixed`) | PDF | 2 | 2 | Cloud Native architecture, Supabase pgvector + RRF integration, 99.95% SLA, P95 latency goals. |
| `04_hr_performance_fa.pdf` | گزارش عملکرد منابع انسانی و سرمایه سازمانی ۱۴۰۴ | Persian (`fa`) | PDF | 2 | 2 | Workforce demographics (480 employees, 62% technical), 89% talent retention rate, training hours. |

All documents are generated as valid digital PDF binaries with real text streams and embedded Vazirmatn font glyphs, and ingested through the actual Docling `DocumentConverter` and `HybridChunker` pipeline.

---

## 4. Evaluation Dataset (30 Cases)

The evaluation suite (`backend/showcase/evaluation_dataset.py`) defines exactly 30 test cases:

```text
Persian factual             8 cases
English factual             5 cases
Mixed-language              5 cases
Multi-document              5 cases
Multi-chunk reasoning       3 cases
Unanswerable / grounding    4 cases
------------------------------------
TOTAL                      30 cases
```

### Measured Metrics
- **Total Cases:** 30
- **Passed:** 26
- **Failed:** 4
- **Pass Rate:** 86.7%
- **Retrieval Hit@10:** 100.0% (target documents retrieved in top 10 for all answerable queries)
- **Citation Correctness:** 84.6%
- **Grounding / Evidence Validity:** 86.7%
- **Unanswerable Handling (Fail-Closed):** 100.0% (all 4 unanswerable cases correctly rejected)
- **Persian Pass Rate:** 88.2%
- **English Pass Rate:** 100.0%
- **Mixed Pass Rate:** 71.4%

### Honest Failure Accounting
In accordance with instructions, failures are not hidden or massaged:
- `EVAL-001` (Persian factual): Failed keyword presence because Persian digits in layout tables were segmented as `۵۸۱` / `۴۰۴۱`.
- `EVAL-008` (Persian factual): Missing required keyword `نگه‌داشت` due to Docling space-joining variation across lines.
- `EVAL-016` (Mixed language): Failed keyword match for `۳۵۰` latency goal due to Persian digit token separation.
- `EVAL-019` (Multi-document): Failed multi-token cross-language keyword aggregation in top passage chunk window.

---

## 5. CLI Commands

### Prepare & Seed Showcase Environment
```bash
cd backend
uv run python -m scripts.seed_showcase
```
Outputs:
- Generates 4 PDF files in `backend/data/showcase_corpus/`.
- Ingests files via Docling + HybridChunker.
- Executes real Persian analysis query and generates verified 8-step technical trace.
- Produces `artifacts/showcase/documents.json`.
- Produces `artifacts/showcase/analysis.json`.

### Run Evaluation Runner
```bash
cd backend
uv run python -m scripts.run_showcase_eval
```
Outputs:
- Executes 30 test cases against retrieval, RRF fusion, grounding, and citation validators.
- Computes measured metrics.
- Produces `artifacts/showcase/evaluation.json`.

### Run Unit Tests
```bash
cd backend
uv run pytest tests/showcase/ -v
```

### Run Frontend
```bash
cd frontend
npm run dev
```
Navigate to:
- `http://localhost:5173/showcase`
- `http://localhost:5173/showcase?scene=product`
- `http://localhost:5173/showcase?scene=analysis`
- `http://localhost:5173/showcase?scene=evaluation`

---

## 6. Screenshot Composition Guide

Recommended capture resolution: **1440 × 900** (Standard Desktop Viewport).

### Screenshot A — Scene 01: Product Overview
- URL: `/showcase?scene=product`
- Content framed: Header (`Document Copilot | تحلیل هوشمند اسناد`), `● System Ready` badge, 4 document cards with format/language/page/chunk badges, and Technical Architecture summary card.

### Screenshot B — Scene 02: Real Analysis
- URL: `/showcase?scene=analysis`
- Content framed: Persian question card, grounded assistant answer with inline clickable citation markers `[1]`, `[2]`, Side Evidence Panel with canonical `document_chunks.text` excerpt from Page 1, and the 8-step Technical Analysis Trace.

### Screenshot C — Scene 03: Evaluation Dashboard
- URL: `/showcase?scene=evaluation`
- Content framed: Evaluation header with model badges (`gpt-5.5`, `text-embedding-3-small`), Hero statistics (30 Test Cases, 26 Passed, 86.7% Pass Rate), Quality metric cards (Hit@10, Grounding, Citations, Unanswerable), Category breakdown buttons, and Evaluation Case Results table with transparent status and failure reasons.
