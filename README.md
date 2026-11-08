# Document Copilot

<div align="center">

![Document Copilot](https://img.shields.io/badge/Document%20Copilot-v1.0.0-blue?style=for-the-badge&logo=openai)
![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136%2B-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React 19](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.9%2B-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![PydanticAI](https://img.shields.io/badge/Orchestration-PydanticAI-E92063?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**Enterprise Multilingual Document Intelligence & Grounded RAG Platform**  
*Grounded, fail-closed financial and corporate intelligence over multi-format filings in Persian & English with click-to-source provenance.*

[Architecture](#-system-architecture) • [Key Capabilities](#-key-capabilities) • [Benchmark Results](#-evaluation--benchmarks) • [Getting Started](#-getting-started) • [API Reference](#-api-reference)

---

</div>

## 📌 Executive Summary

Modern equity analysts, corporate strategists, and compliance officers spend upwards of **50% of their time** manually reviewing multi-hundred-page corporate filings (SEC 10-Ks, 10-Qs, audit statements, and Codal financial reports). Conventional general-purpose LLMs fail in high-stakes enterprise settings due to:
1. **Hallucinations & Ungrounded Speculation:** Generating plausible-sounding financial metrics without source backing.
2. **Bilingual Script Degradation:** Breaking down on Persian/Arabic script nuances (ZWNJ zero-width non-joiners, inconsistent character codepoints, Persian numerals, and right-to-left layout disruptions).
3. **Complex Layout Blindness:** Losing tabular semantics across SEC HTML/PDF financial tables.

**Document Copilot** solves this intake dilemma. It combines **Docling-powered multi-format parsing**, **bilingual hybrid search (`pgvector` + PostgreSQL FTS via Reciprocal Rank Fusion)**, an **agentic PydanticAI reasoning loop**, and an uncompromising **fail-closed LLM grounding judge** that verifies every citation before streaming to analysts.

---

## 🏛 System Architecture

The platform is designed around a three-plane, decoupled architecture:
1. **User Interaction Plane (Frontend SPA):** React 19 + TypeScript powered by Vercel AI SDK v5 for SSE streaming, dynamic citation markers (`[1]`, `[2]`), a contextual Evidence Panel (Side Passage Sheet), and a dedicated `/showcase` analytical suite.
2. **Authoritative Application & Orchestration Plane (FastAPI Backend):** Manages auth, normalization, dual-mode retrieval, Reciprocal Rank Fusion, agent tool calling, and secondary validation.
3. **Storage & Retrieval Plane (PostgreSQL + `pgvector`):** Hosted on Supabase / self-hosted Postgres, housing vector embeddings (`vector(1536)`), normalized lexical representations, generated `tsvector` columns, and relational chat histories.

### High-Level Architecture Diagram

```mermaid
flowchart TB
    subgraph Client["Client Plane (React 19 + TypeScript SPA)"]
        UI["Chat Interface (AI SDK v5 SSE)"]
        CiteViewer["Source Passage Sheet (Evidence Panel)"]
        ShowcaseUI["Showcase & 30-Case Eval Dashboard (/showcase)"]
        AuthClient["Supabase Auth / JWT Client"]
    end

    subgraph API["Authoritative Backend Plane (FastAPI + Python 3.12+)"]
        AuthDep["Auth & JWT Validator"]
        ChatRouter["Chat & Streaming Endpoint (/chat/stream)"]
        DocRouter["Multipart Document Upload (/documents)"]
        ShowcaseRouter["Showcase & Telemetry API (/showcase)"]

        subgraph IngestionPipeline["Document Ingestion Engine"]
            Dispatcher["Format Dispatcher & Magic-Byte Validator"]
            DoclingParser["Docling DocumentConverter (PDF / DOCX / HTML / Image)"]
            OCR["OCR Engine (RapidOCR / Tesseract)"]
            Chunker["HybridChunker (512 tokens, cl100k_base)"]
            NormalizerIngest["Persian Normalizer (Search Text Derivation)"]
            Storage["Content-Hash Local / Cloud Storage"]
        end

        subgraph RetrievalEngine["Hybrid Retrieval & Fusion Engine"]
            QNorm["Query Normalizer (Deterministic NLP)"]
            Embedder["Query Embedding (text-embedding-3-small)"]
            KWExtract["Keyword Extractor (Persian Regex / Fast-path)"]
            RRF["Reciprocal Rank Fusion (k=60)"]
            Hydration["Context Assembler + Neighbor Chunks (r=1)"]
        end

        subgraph AgentOrchestration["Agent & Grounding Plane"]
            Orchestrator["Turn Orchestrator"]
            PydanticAgent["PydanticAI Agent (GPT-5.5 / GPT-4o)"]
            Tools["Bounded Tools (search_filings, read_chunk, read_neighbors)"]
            GroundingJudge["Fail-Closed Grounding Judge (GPT-4.1-mini)"]
        end
    end

    subgraph StoragePlane["Storage & Retrieval Plane (Supabase / PostgreSQL)"]
        PGVector[("pgvector: vector(1536)")]
        PGFTS[("PostgreSQL FTS: tsvector")]
        DocStore[("source_documents & document_chunks")]
        ChatStore[("chat_threads, chat_messages, citations")]
    end

    UI --> ChatRouter
    ShowcaseUI --> ShowcaseRouter
    ChatRouter --> Orchestrator
    DocRouter --> Dispatcher
    Dispatcher --> DoclingParser --> Chunker --> NormalizerIngest --> StoragePlane

    Orchestrator --> QNorm --> Embedder & KWExtract
    Embedder --> PGVector
    KWExtract --> PGFTS
    PGVector & PGFTS --> RRF --> Hydration --> PydanticAgent
    PydanticAgent --> Tools --> Hydration
    PydanticAgent --> GroundingJudge
    GroundingJudge -- "Verified Citations" --> ChatRouter
    GroundingJudge -- "Citation Violation" --> Orchestrator -- "Refuse / Fail Closed" --> ChatRouter
    ChatRouter -- "SSE Stream" --> UI
    UI -. "Inspect Citation" .-> CiteViewer
```

---

## 🔄 End-to-End Request Lifecycle

```mermaid
sequenceDiagram
    autonumber
    actor Analyst as Financial Analyst
    participant UI as React Frontend
    participant API as FastAPI /chat/stream
    participant Norm as Text Normalizer
    participant Ret as Hybrid Retriever (pgvector + FTS)
    participant Agent as PydanticAI Agent
    participant Judge as Fail-Closed Grounding Judge
    participant DB as PostgreSQL Database

    Analyst->>UI: Enters query ("What were AWS growth drivers in 2024?")
    UI->>API: POST /chat/stream (Thread ID, User Message, JWT)
    API->>Norm: Normalize Persian/English typography & ZWNJ
    Norm-->>API: Normalized Query
    API->>Ret: Execute Hybrid Search (Vector + FTS)
    Ret->>DB: Cosine Similarity on document_chunks (k=50)
    Ret->>DB: tsvector Keyword Match on search_text (k=50)
    DB-->>Ret: Candidate Chunks
    Ret->>Ret: Reciprocal Rank Fusion (RRF k=60) + Hydrate Neighbors (r=1)
    Ret-->>Agent: Top-Ranked Grounding Context
    Agent->>Agent: Reason & Synthesize Answer with [n] Citations
    Agent-->>Judge: Proposed Answer + Explicit Citations
    Judge->>Judge: Verify assertion-to-passage semantic containment
    alt Citations Fully Verified
        Judge-->>API: Validation Passed (Provenance Verified)
        API->>DB: Persist Assistant Message + message_citations
        API-->>UI: SSE Stream (Text Deltas + Citation Metadata)
        UI-->>Analyst: Render Answer with Clickable Citation Chips [1][2]
    else Hallucination / Unsupported Assertion Detected
        Judge-->>API: Validation Failed (Fail Closed)
        API-->>UI: SSE Stream (Refusal: "Insufficient evidence in corpus...")
    end
```

---

## ⚡ Key Capabilities

### 1. Fail-Closed Grounding & Guardrails
* **Zero-Hallucination Mandate:** Unlike standard chatbots that assume the LLM's claims are accurate, Document Copilot treats all generation as untrusted output until verified.
* **Secondary LLM Judge:** A specialized grounding judge (`app/grounding/validator.py`) audits every citation `[n]`. It compares the stated factual assertion against the verbatim chunk text stored in PostgreSQL.
* **Fail-Closed Execution:** If an assertion cannot be mapped to an ingested chunk, or if the source passage does not support the claim, the system rejects the answer and emits an evidence deficiency warning.

### 2. Bilingual Persian & English Hybrid Retrieval
* **Deterministic Typography Normalization:** Custom deterministic Persian pre-processor (`app/text/normalize.py`) handling:
  * Zero-Width Non-Joiner (ZWNJ) normalization (`می شود` $\to$ `می‌شود`).
  * Arabic/Persian character normalization (`ي` $\to$ `ی`, `ك` $\to$ `ک`, `ة` $\to$ `ه`).
  * Full conversion of Persian/Arabic numerals to standard digits (`۱۲۳۴۵` $\to$ `12345`).
  * Domain-tuned stop-word removal preserving financial accounting terminology.
* **Reciprocal Rank Fusion (RRF):** Fuses dense vector scores (`text-embedding-3-small`, 1536 dimensions) with sparse full-text lexical ranking using:
  $$RRF\_Score(d) = \sum_{m \in M} \frac{1}{k + r_m(d)} \quad (k=60)$$
* **Context Hydration ($r=1$):** Automatically includes preceding and succeeding adjacent chunks to maintain context across complex financial disclosures and multi-page tables.

### 3. Multi-Format Ingestion Engine
* **Universal Format Support:** Ingests SEC HTML filings, digital and scanned PDFs, Microsoft Word (`.docx`), and financial report images.
* **Layout & Table Preservation:** Powered by Docling 2.0 with semantic table row extraction, ensuring that balance sheets and income statement tables are not destroyed during chunking.
* **Pluggable OCR:** Configurable fallback via RapidOCR / Tesseract for scanned balance sheets and image-based disclosures.
* **Idempotency & Integrity:** Deduplication based on SHA-256 payload content hashes; re-running ingestion skips already processed documents.

### 4. Interactive Showcase & Evidence Mode
* **Instant Evaluation Dashboard (`/showcase`):** Built-in showcase mode displaying 30 real-world benchmark evaluations, interactive telemetry traces, and side-by-side evidence inspection without requiring an active external LLM connection.

---

## 📊 Evaluation & Benchmarks

The system was evaluated against a **30-case benchmark suite** covering bilingual queries, complex multi-document synthesis, numerical extraction, and deliberate adversarial unanswerable traps.

| Metric | Result | Description |
| :--- | :---: | :--- |
| **Retrieval Hit@10** | **100.0%** | The correct grounding chunk was retrieved in the top 10 for every valid test case. |
| **Overall Pass Rate** | **86.7%** | 26 of 30 complex analytical queries passed strict factual verification. |
| **Unanswerable Rejection Rate** | **100.0%** | 4 of 4 out-of-corpus queries were correctly refused without hallucination. |
| **Persian Factual Queries** | **88.2%** | Successful synthesis over Persian financial disclosures and audit notes. |
| **English Factual Queries** | **100.0%** | 5 of 5 SEC filing queries answered with exact citation accuracy. |
| **Citation Correctness** | **84.6%** | Citations linked to the exact underlying financial figures and tables. |

---

## 🛠 Tech Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Backend Framework** | **FastAPI (Python 3.12+)** | High-performance asynchronous REST and SSE streaming service |
| **Agent Framework** | **PydanticAI** | Type-safe LLM agent orchestration with structured output contracts |
| **Database & Search** | **PostgreSQL + pgvector** | Vector similarity search (HNSW) + Full-Text Search (GIN `tsvector`) |
| **ORM & Migrations** | **SQLAlchemy 2.0 + Alembic** | Schema management, type-safe queries, and database versioning |
| **Document Ingestion** | **Docling 2.0 + RapidOCR** | Layout-aware document parsing (PDF, DOCX, HTML, Images) |
| **LLM & Embeddings** | **OpenAI (GPT-5.5 / GPT-4o / text-embedding-3-small)** | Agentic reasoning, embedding, and fail-closed grounding validation |
| **Frontend Framework** | **React 19 + TypeScript + Vite 8** | Modern, type-safe Single Page Application |
| **UI Components & Styling**| **Tailwind CSS v4 + Radix UI + Lucide** | Responsive, accessible, enterprise financial interface |
| **Streaming Protocol** | **Vercel AI SDK v5** | Server-Sent Events (SSE) streaming with structured citation events |

---

## 📂 Repository Structure

```text
document-copilot/
├── AGENTS.md                    # Universal agent guidelines & coding principles
├── README.md                    # Project documentation (this file)
├── PROJECT_AUDIT_REPORT.md      # Comprehensive technical audit report
├── data/                        # Local corpus downloader & sample SEC filings
│   ├── download.py              # SEC EDGAR 10-K automated downloader
│   └── convert_to_markdown.py   # HTML-to-Markdown conversion utility
├── docs/                        # Architectural specifications & sprint milestones
│   ├── architecture.md          # Technical architecture & streaming protocol
│   ├── client-brief.md          # Driftwood Capital client requirements
│   ├── local-persian-migration-audit.md # Self-hosted / vLLM migration roadmap
│   └── sprint-*-report.md       # Sprint engineering reports (Sprints 1 through 5.5)
├── backend/                     # FastAPI backend service
│   ├── alembic/                 # Database migrations (6 revisions)
│   ├── app/
│   │   ├── api/                 # REST endpoints (chat, documents, showcase, auth)
│   │   ├── assistant/           # PydanticAI agent, system instructions, typed deps
│   │   ├── auth/                # Supabase JWT verification dependencies
│   │   ├── chat/                # Orchestration, streaming protocol, conversation persistence
│   │   ├── database/            # SQLAlchemy models (users, chats, chunks, citations)
│   │   ├── grounding/           # Fail-closed citation validation judge
│   │   ├── retrieval/           # Hybrid retriever, pgvector queries, FTS, RRF fusion
│   │   ├── schemas/             # Pydantic schemas for requests and responses
│   │   └── text/                # Persian text normalizer & financial stopwords
│   ├── ingest/                  # Universal multi-format ingestion pipeline
│   ├── showcase/                # Showcase artifacts, telemetry, and evaluation dataset
│   └── tests/                   # Test suite (355+ unit & integration tests)
└── frontend/                    # Vite + React SPA
    ├── src/
    │   ├── components/          # Chat messages, citation chips, evidence panel, UI primitives
    │   ├── hooks/               # Custom hooks (useChatTransport, useAuth)
    │   ├── pages/
    │   │   ├── chat/            # Live chat page & conversation history
    │   │   └── showcase/        # Interactive showcase & 30-case evaluation dashboard
    │   └── lib/                 # HTTP client, Supabase client, environment validation
    ├── package.json
    └── vite.config.ts
```

---

## 🚀 Getting Started

### Prerequisites

Ensure you have the following installed:
* **Python 3.12+** and [**uv**](https://docs.astral.sh/uv/) (Astral's fast Python package manager)
* **Node.js 20+ (LTS)** and **npm** or **pnpm**
* A **Supabase** account (or local PostgreSQL with `pgvector` enabled)
* An **OpenAI API Key**

---

### Step 1: Clone and Configure Environment

```bash
git clone https://github.com/ME0W004/document-copilot.git
cd document-copilot
```

#### Backend Environment
Create `backend/.env`:
```bash
cd backend
cp .env.example .env
```
Fill in the required credentials:
```ini
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-supabase-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-key
DATABASE_URL=postgresql://postgres:password@db.your-project.supabase.co:5432/postgres

OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_CHAT_MODEL=gpt-5.5
OPENAI_GROUNDING_MODEL=gpt-4.1-mini

ALLOWED_ORIGINS=http://localhost:5173
```

#### Frontend Environment
Create `frontend/.env`:
```bash
cd ../frontend
cp .env.example .env
```
Configure backend and auth URLs:
```ini
VITE_API_BASE_URL=http://localhost:8000
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-supabase-anon-key
```

---

### Step 2: Install Dependencies & Run Database Migrations

#### Backend
```bash
cd backend
uv sync --extra ingest
uv run alembic upgrade head
```

#### Frontend
```bash
cd ../frontend
npm install
```

---

### Step 3: Run the Application

#### Start Backend Service
```bash
cd backend
uv run uvicorn app.main:app --reload --port 8000
```
Backend will be available at `http://localhost:8000` (API Docs at `http://localhost:8000/docs`).

#### Start Frontend Client
```bash
cd ../frontend
npm run dev
```
Open your browser at `http://localhost:5173`.

> 💡 **Try Showcase Mode:** Visit `http://localhost:5173/showcase` to explore pre-computed telemetry traces, citation verification walkthroughs, and the 30-case evaluation dashboard without making external LLM calls.

---

## 🧪 Testing & Code Quality

The codebase enforces strict test coverage and static analysis.

### Backend Verification
```bash
cd backend

# Run all unit tests (355 tests, excludes live cloud credentials)
uv run pytest -m "not integration"

# Run full linter and formatting checks
uv run ruff check .

# Run integration tests (requires live Supabase & OpenAI configured in .env)
uv run pytest -m "integration"
```

### Frontend Verification
```bash
cd frontend

# Verify TypeScript compilation and production build
npm run build

# Run ESLint across all components and pages
npm run lint
```

---

## 📡 API Reference Summary

### Core Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/chat/stream` | Streams assistant response via SSE with text tokens and typed citation parts |
| `GET` | `/chat/threads` | Lists analyst conversation threads for authenticated user |
| `POST` | `/chat/threads` | Creates a new chat thread |
| `GET` | `/chat/threads/{id}/messages` | Retrieves message history with attached citation metadata |
| `POST` | `/documents/upload` | Multipart upload for PDF, DOCX, HTML, or images into the ingestion pipeline |
| `GET` | `/showcase/overview` | Returns system overview and capabilities for showcase mode |
| `GET` | `/showcase/analysis` | Retrieves the live verified analysis trace and citation provenance |
| `GET` | `/showcase/evaluation` | Returns the 30-case evaluation dataset, pass rates, and category breakdown |
| `GET` | `/health` | Health check probe returning service status |

---

## 🔒 Security & Data Privacy

* **Strict Row-Level Isolation:** Supabase JWT authentication is enforced on every conversational and document endpoint. Analysts can only access threads they created.
* **Fail-Closed Privacy:** Ingestion content hashes prevent duplicate document uploads and minimize external API token leakage.
* **No Speculative Recommendations:** The agent prompt explicitly prohibits generating unsolicited buy/sell equity recommendations or extrapolating financial numbers beyond verified filings.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
