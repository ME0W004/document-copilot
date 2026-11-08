# Local-First Persian/English Document Copilot — Audit & Migration Plan

**Scope:** audit of the `development` branch of `daveebbelaar/document-copilot` and a precise implementation plan for converting it into a fully local, self-hosted, Persian/English document copilot.
**Status:** AUDIT + PLAN ONLY. No application code was modified in producing this document.
**Workspace note:** the working copy at `D:\document-copilot-development` is a snapshot of the `development` branch (no `.git` directory present). Branch identity was verified from content: the codebase contains the full completed stack (PydanticAI agent, hybrid retrieval, grounding validator, citation UI) described by `docs/architecture.md` and `docs/todos.md` — the educational `main` branch would not contain these.

---

## 1. Executive Summary

The application is a **fully working grounded RAG chat product** over a small SEC 10-K corpus: FastAPI backend, PydanticAI agent with 4 bounded retrieval tools, fail-closed citation validation backed by an LLM judge, hybrid pgvector + Postgres full-text retrieval fused with Reciprocal Rank Fusion, and a polished React (Vercel AI SDK v5) chat frontend with clickable citations and a source-passage viewer.

**The good news — the architecture is far more portable than the README suggests:**

1. **Supabase is already only "half-used."** Retrieval, chunk hydration, and citation-context queries go through **direct Postgres via SQLAlchemy + psycopg** (`backend/app/database/session.py`). Supabase is used for (a) auth-token verification, (b) thread/message/citation persistence via its REST client, and (c) RLS policies. Replacing it is a bounded, mechanical refactor, not a redesign.
2. **pgvector and hybrid retrieval are plain Postgres features** — they survive the Supabase removal unchanged.
3. **The LLM boundary is already an abstraction in practice.** All generation flows through PydanticAI (`backend/app/assistant/agent.py`), which accepts any OpenAI-compatible `base_url`. Qwen through Ollama/vLLM is a *configuration* change plus small code changes in two helper paths (`grounding/validator.py`, `retrieval/keywords.py`) that call the OpenAI SDK directly.
4. **The grounding philosophy (TurnRegistry allowlist, fail-closed validator, insufficient-evidence contract) is provider-agnostic by design** and must be preserved exactly.
5. **No Supabase Storage and no upload API exist.** Documents are local files ingested by CLI scripts — the "storage" problem for local deployment is trivial.

**The hard parts (the real work):**

1. **Persian full-text search is structurally absent.** PostgreSQL ships **no Persian text-search configuration** (no stemmer, no stopwords). The schema hard-codes `to_tsvector('english', text)` (migration `backend/alembic/versions/3c81ca3fef26_initial_schema.py:127-132`), and `plainto_tsquery('english', ...)` ANDs all query words — long Persian queries will return zero rows. A Persian normalization layer + a new search representation is **new subsystem work**, not a config change.
2. **The FTS keyword extractor (`backend/app/retrieval/keywords.py`) is English-only by construction.** Its regexes (`[A-Za-z0-9]...`) cannot match Persian characters at all; its deterministic fallback silently strips Persian tokens. It must be replaced/augmented.
3. **Ingestion is HTML-only.** `backend/ingest/chunking.py` parses SEC EDGAR HTML with Docling. There is no PDF path and no OCR. PDF/OCR support is additive (Docling already bundles PDF + OCR engines), but page/section metadata and the "table row" pipeline are SEC-specific.
4. **Persian UI readiness is zero** on the frontend: `lang="en"`, no `dir`, no RTL styles, Geist fonts (no Arabic-script glyphs), all UI copy hard-coded English, no i18n layer.
5. **Embeddings are dimension-locked at 1536** (`text-embedding-3-small`) in four places (config default, `constants.py`, migration, runtime checks). BGE-M3 (1024-dim) requires a schema migration + full re-embed.

**Verdict on the proposed model direction (detailed in §15/§19):** BGE-M3 + Qwen (Ollama or vLLM, OpenAI-compatible) + local PostgreSQL/pgvector + local inference is a **good fit** — it matches the code's existing seams. The only mandatory correction to the plan as proposed: the **FTS side cannot stay "just switch config to Persian"** — Postgres has no Persian config; the plan must include an application-level Persian normalizer and a normalized search representation (plus `pg_trgm` for fuzzy matching). The **reranker is genuinely missing** and is the right place to compensate for the loss of English-grade stemming/lexical ranking.

---

## 2. Current `development` Architecture

### 2.1 Services and entry points

| Piece | File | Notes |
| --- | --- | --- |
| FastAPI app | `backend/app/main.py` | CORS from settings, `GET /health`, includes `auth` + `chat` routers |
| Auth routes | `backend/app/api/auth.py` | `GET /me` only |
| Chat routes | `backend/app/api/chat.py` | `/chat/threads` (list/create), `/chat/threads/{id}/messages`, `/chat/citations/{chunk_id}/context`, `POST /chat/stream` (SSE) |
| Config | `backend/app/config.py` | single `Settings` (pydantic-settings), fail-fast on missing env |
| Agent | `backend/app/assistant/agent.py` | PydanticAI `Agent`, `OpenAIChatModel` + `OpenAIProvider`, tools, `UsageLimits` |
| Orchestration | `backend/app/chat/orchestrator.py` | `run_turn`: agent run → prune citations → validate (2 attempts) → stream → persist |
| Streaming | `backend/app/chat/streaming.py` | AI SDK-compatible SSE; **word-by-word re-chunking of the finished answer** (no live token stream) |
| Grounding | `backend/app/grounding/validator.py` | fail-closed validator + `OpenAIGroundingJudge` via `chat.completions.parse` |
| Retrieval | `backend/app/retrieval/{retriever,queries,fusion,keywords,embeddings,types}.py` | hybrid pgvector + FTS, Python RRF |
| DB access | `backend/app/database/` | split brain: SQLAlchemy/psycopg direct Postgres (retrieval, documents) **and** Supabase REST client (auth, chats, users) |
| Ingestion | `backend/ingest/{chunk_and_embed,chunking,embeddings,load_source_documents,sec_tables}.py` | CLI-only; Docling on local SEC HTML |
| Migrations | `backend/alembic/versions/` | 4 revisions; vector ext, `vector(1536)`, generated `tsvector('english')`, HNSW + GIN indexes, Supabase RLS |
| Frontend | `frontend/src/` | React 19 + Vite + Tailwind 4 + shadcn + AI SDK v5 (`ai@^5`, `@ai-sdk/react@^2`) |
| Deploy | `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/Caddyfile` | two Railway services; **no docker-compose** |

### 2.2 Two parallel database clients (important for the Supabase audit)

- **Direct Postgres (SQLAlchemy, psycopg v3):** `app/database/session.py:get_session()` → used by `app/retrieval/retriever.py`, `app/retrieval/queries.py`, `app/database/documents.py`, `app/assistant/tools.py`, `app/api/chat.py:load_citation_context`, and both `ingest/` pipelines. This is plain Postgres access — no Supabase API involved.
- **Supabase REST (PostgREST):** `app/database/supabase.py` (`get_service_role_client`, `create_user_client`) → used by `app/auth/dependencies.py`, `app/database/users.py:ensure_user`, `app/database/chats.py` (all thread/message/citation persistence), `app/api/chat.py` route handlers.

Ownership enforcement today is **duplicated**: RLS policies in SQL (migration `3c81ca3fef26`, using `auth.uid()`) *and* explicit Python checks in `app/database/chats.py:require_thread_access` via the service-role client. The Python check alone is sufficient after migration.

---

## 3. Actual End-to-End Data Flow

### 3.1 Ingestion path (offline, CLI)

| Stage | File / function | Library | Provider | DB | Network | Config |
| --- | --- | --- | --- | --- | --- | --- |
| 1. Download corpus | `data/download.py` | stdlib `urllib` | SEC EDGAR | – | HTTPS | `USER_AGENT`, `TICKERS` consts |
| 2. HTML → Markdown | `data/convert_to_markdown.py` (Docling `DocumentConverter`) + table extraction `ingest/sec_tables.py:extract_sec_tables` | docling | – | – | – | `manifest.json` |
| 3. Load metadata | `ingest/load_source_documents.py:load_source_documents` | SQLAlchemy | – | INSERT `source_documents` (incl. `markdown_content`) | Postgres | `MARKDOWN_DIR` |
| 4. Parse + chunk | `ingest/chunking.py:chunk_document(html_path, filing_metadata)` → Docling `HybridChunker` (`build_hybrid_chunker`, `CHUNK_MAX_TOKENS=512`), tokenizer = `PatchedOpenAITokenizer` over **tiktoken `cl100k_base`**; tables → row-level chunks via `ingest/sec_tables.py` | docling, tiktoken | – | – | – | `CHUNK_MAX_TOKENS` |
| 5. Embed | `ingest/embeddings.py:embed_texts` (batch 100, `dimensions=settings.openai_embedding_dimensions`) | openai SDK | **OpenAI** | – | HTTPS | `OPENAI_*` |
| 6. Persist | `ingest/chunk_and_embed.py:ingest_document` → INSERT `document_chunks` (+ `document_tables`); `search_vector` is a **generated column** (no write) | SQLAlchemy | – | `document_chunks`, `document_tables` | Postgres | – |
| Idempotency | `_document_has_chunks` skip / `--force` → `_delete_chunks` (also deletes `message_citations` first — FK is `ON DELETE RESTRICT`) | | | | | |

**No PDF, DOCX, or OCR anywhere.** Page numbers come from Docling provenance (`chunking.py:_page_from_chunk_meta`) — mostly `None` for EDGAR HTML (no page concept); sections come from Docling headings or the regex `_ITEM_SECTION_RE = re.compile(r"\bItem\s+[\dA-Z.]+\b")` (`chunking.py:31`) — English/SEC-specific.

### 3.2 Chat turn (request path)

| Stage | File / function | Provider | DB | Notes |
| --- | --- | --- | --- | --- |
| Auth | `frontend/src/hooks/useSession.ts` → `lib/api.ts:getAccessToken` → Bearer header; backend `app/auth/dependencies.py:get_current_user` verifies JWT via **Supabase Auth** (`acreate_client(...).auth.get_user(jwt=...)`) | Supabase | – | `CurrentUser(id, email)` |
| Thread access | `app/database/chats.py:require_thread_access` (service-role client, Python ownership check) | Supabase REST | `chat_threads` | raises 404/403 |
| User upsert | `app/database/users.py:ensure_user` (service role) | Supabase REST | `users` | mirrors `auth.users` |
| Extract query | `app/chat/messages.py:extract_last_user_message`, `text_from_parts` | – | – | AI SDK `UIMessage` → text |
| Embed query | `app/retrieval/embeddings.py:embed_query` (OpenAI, `dimensions` param, dims check) | **OpenAI** | – | runs in `ThreadPoolExecutor` |
| FTS keywords | `app/retrieval/keywords.py:extract_fts_keywords` — fast path ≤5 tokens; else **OpenAI `chat.completions.parse`** (`gpt-4.1-mini`) with English-only heuristics + `_deterministic_fallback` | **OpenAI** | – | English stopword lists |
| Dual search | `app/retrieval/retriever.py:_dual_search` → `queries.py:semantic_search` (`embedding <=> CAST(:query_vec AS vector)`, cosine) and `queries.py:full_text_search` (`plainto_tsquery('english')` + `ts_rank_cd`) over `document_chunks` JOIN `source_documents`; filters ticker/form/fiscal_year | – | Postgres (pgvector + GIN) | separate sessions per leg |
| Fusion | `app/retrieval/fusion.py:reciprocal_rank_fusion` (`k=60`), top-k=10 | – | – | pure Python |
| Hydrate | `app/database/documents.py:get_chunks_by_ids`, `get_surrounding_chunks` (neighbors radius 1) | – | Postgres | passages = `app/retrieval/types.py:RetrievedPassage` |
| Agent | `app/assistant/agent.py:run_document_agent` → `Agent.run_sync` in `asyncio.to_thread`; tools `app/assistant/tools.py:search_filings/read_chunks/read_chunk/read_surrounding_chunks`; each tool result registers passages into `TurnRegistry` (citation allowlist, `app/assistant/deps.py`) | **OpenAI** (chat model `gpt-5.5` default in config; `.env.example` says `gpt-4.1`) | – | output type `GroundedAnswer` (`answer`, `citations[{citation_index, chunk_id, excerpt}]`, `insufficient_evidence`) |
| Status events | `app/assistant/status.py` → `on_status` → thread-safe queue → SSE `data-status` parts (`app/chat/streaming.py:stream_status`) | – | – | UI pipeline stages |
| Validate | `app/chat/orchestrator.py`: `prune_unreferenced_citations` → `GroundingValidator.validate` (`app/grounding/validator.py`): markers must match indices exactly, chunk must be in registry, **LLM judge** (`OpenAIGroundingJudge.chat.completions.parse`, `gpt-4.1-mini`) must support every citation; fail-closed; 1 retry (`MAX_VALIDATION_ATTEMPTS=2`) | **OpenAI** | – | `GroundingJudge` Protocol exists |
| Stream | `app/chat/streaming.py:stream_grounded_turn_and_persist` → fake word-by-word `text-delta` SSE, then `data-citation` parts, then `finish`; on validation failure streams `GROUNDING_FAILURE_MESSAGE` | – | – | AI SDK wire format |
| Persist | `app/database/chats.py:append_grounded_turn` (user-scoped Supabase client): INSERT `chat_messages` (user + assistant `parts` JSONB), INSERT `message_citations`, UPDATE `chat_threads.updated_at`/title | Supabase REST | 3 tables | runs in `finally` |
| Citation context | Frontend `SourcePassageSheet` → `GET /chat/citations/{chunk_id}/context` → `app/api/chat.py:load_citation_context` → `app/database/documents.py:get_chunk_context` (SQLAlchemy direct) | – | Postgres | previous/anchor/next + optional table markdown |

---

## 4. OpenAI Dependency Map

Direct SDK usage (`openai==2.38.0` in `backend/pyproject.toml:13`) — every call site:

| # | Component | File | Current OpenAI dependency | Why it is used | Replace with | Difficulty |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Chat agent model | `backend/app/assistant/agent.py:31-41` (`OpenAIChatModel`, `OpenAIProvider(api_key=...)`) | Chat completions via PydanticAI; model `settings.openai_chat_model`; tool-calling loop | Answer generation | PydanticAI `OpenAIChatModel` with `OpenAIProvider(base_url=settings.llm_base_url, api_key=...)` pointed at Ollama (`http://ollama:11434/v1`) or vLLM; model name `Qwen...` | **Low** — PydanticAI natively supports OpenAI-compatible endpoints |
| 2 | Grounding judge | `backend/app/grounding/validator.py:66-98` (`OpenAIGroundingJudge`, `chat.completions.parse(..., response_format=CitationGroundingDecisionList)`) | Structured output (JSON schema `response_format`) | Verify each citation is supported by its chunk | Same judge behind the OpenAI-compatible endpoint; vLLM supports `json_schema` response_format; Ollama supports structured outputs. Keep the existing `GroundingJudge` Protocol; add fallback JSON-parse path if a server lacks strict mode | **Medium** — structured-output support varies across local servers |
| 3 | Query embedding | `backend/app/retrieval/embeddings.py:embed_query` | `embeddings.create(model, dimensions=1536)` + dims check | Live query vector | `EmbeddingProvider` (new, §15.2) → BGE-M3 (1024-dim). **Drop the `dimensions` kwarg — it is an OpenAI Matryoshka-truncation feature; BGE-M3 has fixed 1024 dims** | **Low-Medium** (plus schema migration + re-index) |
| 4 | Ingest embedding | `backend/ingest/embeddings.py:embed_texts` (batch 100) | same | Corpus vectors | Same provider; batch size configurable (Ollama/TEI accept arrays; tune batch for CPU) | **Low-Medium** |
| 5 | FTS keyword extraction | `backend/app/retrieval/keywords.py:241-273` (`chat.completions.parse(response_format=FtsKeywordExtraction)`) | Structured output | Shrink long queries to ≤5 AND-able FTS words | Replace with normalizer + local LLM keyword step (or drop LLM step for Persian: normalized token extraction + stopword removal is deterministic) | **Medium** — logic is English-specific end to end |
| 6 | Tokenizer | `backend/ingest/chunking.py:20,34-44,90-94` — `docling_core...tokenizer.openai.OpenAITokenizer` wrapping **tiktoken `cl100k_base`** | Token counting for chunk size (512) | Chunk budget | Keep tiktoken as a *counting heuristic* (works on Persian, just less efficient) **or** swap to a HuggingFace tokenizer matching the embedding model. Works either way; not a hard coupling | **Low** |
| 7 | Config/env | `backend/app/config.py:21-27`, `backend/.env.example:18-26` | `OPENAI_API_KEY`, model names, dims, temperature, request limit | Settings | New provider-neutral settings block (`llm_*`, `embedding_*`, `rerank_*`) with OpenAI-compatible defaults | **Low** |
| 8 | Hard-coded dims | `backend/app/database/models/constants.py:2` (`EMBEDDING_DIMENSIONS = 1536`), `backend/alembic/versions/3c81ca3fef26_initial_schema.py:22,95` (`Vector(1536)`), runtime len checks in both embedding modules | Schema + validation | Column type | 1024 (BGE-M3) via new migration; make `EMBEDDING_DIMENSIONS` read from settings | **Medium** (migration + full re-embed) |
| 9 | pyproject | `backend/pyproject.toml:13` (`openai==2.38.0`) | SDK for 1-5 | HTTP client | Keep the package (it is the OpenAI-compatible client for Ollama/vLLM/TEI too) — this is the standard way to talk to local servers | **None** (keep) |

**Assumptions that are OpenAI-specific but harmless or already decoupled:**
- **Streaming:** there is *no* live LLM streaming to break — `app/chat/streaming.py:_text_events` fake-streams the finished answer word-by-word. The app is already provider-agnostic here (and this is the ideal place to later add real token streaming for slower local models).
- **Retry/error logic:** none custom — failures propagate to the orchestrator's `except` (`app/chat/orchestrator.py:90-93`) or the validator's fail-closed path. No OpenAI-specific retry code to port.
- **Token-usage reporting:** `agent.py:56-63` reads PydanticAI's normalized `usage` object — provider-agnostic.
- **Indirect:** `docling-core`'s `OpenAITokenizer` is just a tiktoken wrapper (item 6); Vercel AI SDK on the frontend never talks to OpenAI (transport points at FastAPI, `frontend/src/hooks/useChatTransport.ts:53`).
- **Tests:** no test file imports `openai` or `supabase` — unit tests patch at module boundaries (`tests/retrieval/test_retriever.py` patches `embed_query`, `extract_fts_keywords`, `semantic_search`, `full_text_search`; `tests/grounding/test_validator.py:35` defines `FakeGroundingJudge`). Only the 2 `@pytest.mark.integration` files (`tests/retrieval/test_retriever_integration.py`, `tests/assistant/test_agent_integration.py`) hit live services.

---

## 5. Supabase Dependency Map

Direct usage (`supabase==2.30.0` backend; `@supabase/supabase-js@^2.107.0` frontend):

| # | Concern | File(s) | What it does today | Local replacement | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | JWT verification | `backend/app/auth/dependencies.py:get_current_user` | Per-request HTTP call to Supabase Auth (`auth.get_user(jwt)`) | Local JWT (HS256) issued by `/auth/login`/`/auth/signup`; verify signature locally | Keep `get_access_token` + `CurrentUser(id, email)` dependency signatures — routes unchanged |
| 2 | User-scoped REST client | `backend/app/database/supabase.py:create_user_client` | PostgREST calls carrying the user JWT so RLS applies | **Delete.** Replace call sites with SQLAlchemy sessions | Ownership checks already exist in Python (`require_thread_access`) |
| 3 | Service-role client | `backend/app/database/supabase.py:get_service_role_client` | `ensure_user` upsert; `require_thread_access` read | SQLAlchemy session | – |
| 4 | User provisioning | `backend/app/database/users.py:ensure_user` | Upserts Supabase-auth user into `users` (id = `auth.users.id`) | Local `/auth/signup` inserts the `users` row directly (id = generated UUID) | `users.id` stays a plain UUID PK; no FK to any auth schema |
| 5 | Chat persistence | `backend/app/database/chats.py` (all functions) | Thread CRUD, message history, citations hydration, `append_grounded_turn` via PostgREST | Port to SQLAlchemy (queries are simple selects/inserts; `require_thread_access` keeps its Python ownership check) | Mechanical, well-isolated file |
| 6 | Route wiring | `backend/app/api/chat.py` (`create_user_client(access_token)` in 5 handlers) | Passing user-scoped client into `chats.py` | Pass `Session` instead | Handler bodies shrink |
| 7 | RLS + `auth.uid()` | `backend/alembic/versions/3c81ca3fef26_initial_schema.py:276-488`, `b7f4a1c2d9e8:60-69` | Policies on 7 tables for role `authenticated` | Drop policies (single local operator) or keep tables unpoliced; keep the Python ownership checks | RLS *concept* (user-scoped rows) survives in `require_thread_access` |
| 8 | Frontend auth client | `frontend/src/lib/supabase.ts`, `lib/env.ts:12` | Browser Supabase client | Token store (localStorage) + `/auth` API calls | Small module |
| 9 | Frontend session | `frontend/src/hooks/useSession.ts` | `getSession` + `onAuthStateChange` | Local `useSession` reading the token store | Same `Session|null` return shape to minimize churn |
| 10 | Login/SignUp/SignOut | `frontend/src/pages/Login.tsx:22`, `SignUp.tsx`, `components/chat/UserMenu.tsx:34`, `components/ProtectedRoute.tsx`, `PublicRoute.tsx` | `signInWithPassword` / `signUp` / `signOut` | POST `/auth/login`, `/auth/signup`, client-side logout | UI components reusable as-is |
| 11 | Token injection | `frontend/src/lib/api.ts:getAccessToken` | Supabase session → Bearer | Token store | One function |
| 12 | Env vars | `backend/app/config.py:16-18`, `backend/.env.example:4-8`, `frontend/.env.example:11-13`, both Dockerfiles | `SUPABASE_*`, `VITE_SUPABASE_*` | Removed; replaced by `AUTH_SECRET`, DB URL | Also `docs/guides/supabase-setup.md`, `railway-deployment.md` become obsolete |

**What is "Supabase" in name only (KEEP):** `pgvector` (architecture docs call it "Supabase pgvector", but `backend/app/retrieval/queries.py` uses plain SQL through psycopg), Postgres itself, the whole schema in `app/database/models/`, Alembic (`DATABASE_URL` points at any Postgres), and the `Vector` type from `pgvector==0.4.2`.

**What survives conceptually:** user-scoped data isolation (via `require_thread_access` + FK cascades `chat_threads→users→chat_messages→message_citations`), the `users` mirror table, the "backend is the only privileged writer" boundary.

**Storage:** Supabase Storage is **not used anywhere**. Raw filings live on the local filesystem (`data/downloads/`, `data/markdown/`; `ingest/chunking.py:28-29`). Local deployment needs only a data directory/volume — no storage layer rewrite.

---

## 6. Retrieval Architecture Audit

### 6.1 What exists

**Hybrid retrieval** (`app/retrieval/retriever.py:DocumentRetriever.search`):
1. `embed_query(query)` (OpenAI) and `extract_fts_keywords(query)` (LLM fast-path/deterministic) run in parallel (`retriever.py:67-71`).
2. `_dual_search` runs both SQL queries in parallel threads with separate sessions (`retriever.py:134-164`).
3. `reciprocal_rank_fusion([semantic_ids, fts_ids], k=60)` in pure Python (`fusion.py`), `top_k=10` (`retriever.py:82-85`).
4. Hydration: `get_chunks_by_ids` + `get_surrounding_chunks` (radius 1) with dedup (`retriever.py:90-131`).

**SQL** (`app/retrieval/queries.py`):
- Semantic: `1 - (dc.embedding <=> CAST(:query_vec AS vector)) AS score` — pgvector **cosine distance**, HNSW-indexed; vector passed as a string literal → **SQL is dimension-agnostic**; only the column type and the client-side dim check know 1536.
- Lexical: `ts_rank_cd(dc.search_vector, plainto_tsquery('{fts_config}', :query_text))` with `fts_config` from settings (**default `'english'`**, `config.py:33`).
- Filters: `sd.ticker = :ticker`, `sd.form = :form`, `sd.fiscal_year = ANY(:fiscal_years)` (`queries.py:25-45`).

Answers to the required questions:
1. **Vector-only, lexical-only, or hybrid?** True hybrid with Python RRF.
2. **DB operators?** `<=>` (cosine), `plainto_tsquery`, `ts_rank_cd`, `@@`, HNSW + GIN indexes (migration `3c81ca3fef26:134-154`).
3. **Dimension assumed?** 1536.
4. **Where defined?** `app/database/models/constants.py:2`, `app/config.py:23` (`openai_embedding_dimensions: int = 1536`), `alembic/versions/3c81ca3fef26_initial_schema.py:22,95`, and runtime length checks in `app/retrieval/embeddings.py:21-25` and `ingest/embeddings.py:32-36`.
5. **Coupling to OpenAI embeddings?** The SQL is agnostic; coupling is concentrated in `embed_query`/`embed_texts` + the `dimensions=` kwarg + the dim constants. Clean seam.
6. **Can BGE-M3 be introduced cleanly?** Yes — behind an `EmbeddingProvider`; requires one migration (column type) and full re-ingest (embeddings only; text chunks survive).
7. **Schema migration needed?** Yes: `ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(1024)` (or new column + backfill + swap; either rewrites the table — corpus is small, fine), rebuild HNSW, and re-add the generated `search_vector` (generated-column expressions cannot be altered in place; see §12/§18).
8. **Multilingual/Persian support?** Currently none — see 6.2.
9. **Reranker present?** **No.** RRF is the only fusion; nothing re-scores after fusion.
10. **Where should a reranker go?** In `DocumentRetriever._search_with_session`, **after RRF truncation and before hydration/neighbor expansion** (`retriever.py:82-92`): rerank the `candidate_k`-fused pool (e.g. top 20-30) with a cross-encoder (BAAI/bge-reranker-v2-m3 served locally), then take `top_k`. A `RerankerProvider` protocol with a pass-through default keeps it optional and testable.

### 6.2 Persian search problems — concrete defects in the current code

| Persian issue | Current behavior | Where it bites |
| --- | --- | --- |
| **No Postgres Persian FTS config exists** (no stemmer/stopword dictionary ships with PostgreSQL) | `to_tsvector('english', text)` on Persian text: the default parser tokenizes OK, but Persian words are **not stemmed** and Persian stopwords (و، را، با، این، از، به، که…) are **not removed** | Generated column `3c81ca3fef26:127-132`; query side `queries.py:100` |
| **`plainto_tsquery` ANDs every word** | Long Persian questions → zero matches | `queries.py:95-105` |
| **ي (U+064A Arabic) vs ی (U+06CC Persian)**, **ك (U+0643) vs ک (U+06A9)** | No canonicalization anywhere; text typed with Arabic codepoints (common when content arrives via copy-paste or OCR) never matches Persian-typed queries | Ingestion + query paths |
| **نیم‌فاصله (ZWNJ, U+200C)** — می‌شود / می شود / میشود | Postgres' default parser treats ZWNJ as a token separator, so ZWNJ-inconsistent forms tokenize differently → misses; no normalization exists | Ingestion + query paths |
| **Arabic-Indic ٠-٩ (U+0660) vs Persian ۰-۹ (U+06F0) vs ASCII digits** | No mapping; numeric queries ("۱۴۰۲" vs "1402") miss | Ingestion + query paths |
| **Diacritics (ِ ُ َ ّ ْ etc.)** | Kept as part of tokens → split lexemes | Ingestion |
| **Mixed Persian/English** (e.g. "نرخ بهره فدرال رزرو در 10-K") | FTS leg: `'english'` config handles the English tokens but not the Persian ones; semantic leg is the only effective channel today | `queries.py` |
| **`keywords.py` cannot see Persian at all** | `_capitalized_tokens` regex `[A-Za-z][A-Za-z0-9]*` (`keywords.py:158`) and `_deterministic_fallback` regex `[A-Za-z0-9][A-Za-z0-9\-/]*` (`keywords.py:218`) match **ASCII only** — Persian tokens are silently dropped; if nothing survives, `_deterministic_fallback` returns the raw query, which `plainto_tsquery` ANDs into zero rows | `keywords.py:154-169, 217-229` |
| **tiktoken `cl100k_base` on Persian** | ~2-4 tokens per Persian word → 512-token chunks hold fewer Persian words than intended; counting is still *consistent*, so this degrades chunk density, not correctness | `chunking.py:92` |

**Recommended normalization design (where it should occur): both sides, as a separate normalized search representation.**

- New module `backend/app/text/normalize.py` (single source of truth): Arabic→Persian codepoint mapping (ي→ی, ك→ک, ة→ه, …), digit mapping (۰-۹ and ٠-٩ → ASCII), ZWNJ canonicalization (normalize `X\u200cY` variants; decide policy: keep ZWNJ as part of tokens for embedding, and *also* emit a ZWNJ→space variant for FTS tokens), diacritic stripping, punctuation folding, whitespace collapsing, optional light suffix folding (ها، های، تر، ترین) as a conservative stemmer.
- **Ingestion:** store `document_chunks.search_text = normalize(text)` (new column) alongside the untouched `text` (which remains the citation/excerpt source — the validator requires *verbatim* excerpts, so the original text must never be replaced).
- **DB:** regenerated `search_vector = to_tsvector('simple', search_text)` with GIN index (the `'simple'` config just lowercases/lexemizes — all real work is done by our normalizer), plus a `pg_trgm` GIN index on `search_text` for fuzzy/substring matching (prefixes, OCR noise, morphology that survives stemming).
- **Query path:** `normalize(query)` before both embedding and FTS keyword generation; the FTS leg becomes: deterministic Persian-aware keyword selection (tokens minus stopwords, ≤5 words) with the LLM extractor kept as an optional refinement for English.
- **Embedding path:** BGE-M3 is multilingual and *does* handle raw Persian, but feeding it normalized text (consistent ZWNJ/codepoints) measurably improves consistency; normalization before embedding is recommended and cheap.

---

## 7. Ingestion Architecture Audit

Current state (all in `backend/ingest/`):

- **Formats:** SEC EDGAR **HTML only**. `chunking.py:convert_html_to_document` → Docling `DocumentConverter`; `data/convert_to_markdown.py` produces the Markdown mirror stored in `source_documents.markdown_content`.
- **Parser:** Docling 2.96 (`pyproject.toml:28`, optional `ingest` extra). PDF and DOCX readers and OCR engines (Tesseract/EasyOCR/RapidOCR) ship inside Docling but are **unused** — the natural extension point for the target pipeline.
- **Chunking:** `HybridChunker` with `PatchedOpenAITokenizer` (tiktoken `cl100k_base`), `CHUNK_MAX_TOKENS = 512`, `merge_peers=True`, `repeat_table_header=True`, tables serialized to Markdown (`chunking.py:97-106`). **No explicit overlap** (HybridChunker splits token-aware without overlap; neighbor chunks at query time substitute for overlap).
- **Metadata:** `page` (Docling provenance; mostly `None` for HTML), `section` (headings or `Item N` regex — SEC-specific, `chunking.py:31,135-143`), `token_count`, `chunk_metadata` JSONB (filing metadata + `chunk_kind` narrative|table_row + raw text + full Docling meta dump; table rows embed the whole table dict and link to `document_tables` via `table_id`).
- **Tables:** bespoke SEC table extractor `ingest/sec_tables.py` (HTMLParser + regexes for `$1,234` amounts, units like "(in millions)", XBRL `ix:nonfraction` facts) → per-row chunks so numeric cells are individually retrievable. **This is the most SEC-specific code in the repo** and will not apply to arbitrary Persian documents; keep it for the legacy corpus, and let generic Docling table serialization handle new formats.
- **Failure handling:** fail-loud exceptions per document (`FileNotFoundError`, `ValueError`), sequential loop, no partial-state cleanup needed because chunks are written in one transaction per document (`chunk_and_embed.py:161`).
- **Duplicates/re-index:** `accession_number` unique constraint; `skip_existing` by chunk existence; `--force` deletes chunks + `message_citations` (FK `RESTRICT` forces explicit citation deletion, `chunk_and_embed.py:54-64`) + `document_tables`, then re-ingests.
- **Storage of originals:** local filesystem only (`data/downloads/`, `data/markdown/`); `source_documents.markdown_content` holds the normalized text in-DB.

**Suitability for Persian documents:** unsuitable as-is — no PDF, no OCR, English-only section detection, no normalization, tokenizer tuned for English. But the *shape* of the pipeline (parse → chunk → embed → persist, CLI, idempotent) is right.

**Target Persian pipeline — exact insertion points (do NOT implement yet):**

Digital PDF: `PDF → DocumentConverter (PdfPipelineOptions, do_ocr=False) → DoclingDocument → [NEW: persian normalize → search_text] → HybridChunker (unchanged mechanics) → EmbeddingProvider → document_chunks`.
- Insert a **format dispatcher** in `chunk_and_embed.ingest_document` where `html_path_for_accession(...)` is called (`chunk_and_embed.py:109-115`): accept a document record with a file path + format instead of assuming HTML-from-manifest.
- Page numbers: Docling provenance gives real pages for PDFs — `_page_from_chunk_meta` (`chunking.py:119-132`) already consumes it; this materially **improves** citations (`p.{page}` appears in agent passages and the source sheet).
- Section detection: replace the `Item` regex fallback with a pluggable section策略 (Docling headings first; Persian heading heuristics later).

Scanned PDF: same, with `do_ocr=True` + `ocr_lang="fas"` (Tesseract `fas` traineddata) or EasyOCR `fa`; insert **OCR-quality guardrails** (confidence/length sanity checks) where `ChunkRecord`s are built (`chunking.py:map_chunk_record`). Flag: Tesseract's `fas` model is mediocre on low-quality scans — budget for an OCR-engine comparison during implementation (see Risk Register).

Add (new, missing): an **upload/registration API + local storage** for user documents (today ingestion is a developer CLI against a hardcoded `data/` manifest), and a `language`/`source_format` column on `source_documents`.

---

## 8. LLM / Agent / Grounding Audit

**Is it agentic?** Yes, genuinely: PydanticAI `Agent` (`app/assistant/agent.py`) runs a multi-step tool loop (request limit 20, temperature 0) over four bounded tools (`app/assistant/tools.py`): `search_filings` (hybrid retrieval + registry registration), `read_chunks`, `read_chunk`, `read_surrounding_chunks` (DB reads + registration). Tools return grep-style formatted passages (`app/retrieval/types.py:format_passages_for_agent`, 800-char excerpts, 12k-char cap). Context assembly = tool results; there is no monolithic prompt stuffing.

**Citation generation & validation** (`app/grounding/validator.py` + `app/assistant/outputs.py`):
- Model emits `[n]` markers in `answer` and a `citations` list with `chunk_id` + **verbatim `excerpt`**.
- `TurnRegistry` (`app/assistant/deps.py:16-29`) is the citation allowlist: every chunk surfaced to the model this turn (including neighbors) is registered; `validator.py:196-202` rejects any citation whose `chunk_id` was never retrieved (fail-closed).
- `validate()` enforces: non-empty answer; `insufficient_evidence` ⇒ zero citations and vice versa grounded answers need ≥1; unique, contiguous 1-based indices; `[n]` markers must exactly match citation indices; LLM judge (`OpenAIGroundingJudge`, structured output, temperature 0) must mark every citation supported; index-repair path re-judges one-by-one if the judge misaligns (`validator.py:131-142`).
- Orchestrator retries the whole turn once on validation failure (`chat/orchestrator.py:25,67-107`), then streams a controlled failure (`chat/streaming.py:18-21` GROUNDING_FAILURE_MESSAGE) instead of an unverifiable answer. **This philosophy must be preserved exactly** — it is the product.

**Unsupported information:** handled at three layers — instructions.md forbids invention; `insufficient_evidence` flag; validator fail-closed. 

**Streaming:** `agent.run_sync` (blocking, in a worker thread) + status events pumped to SSE; the answer is then **fake-streamed word-by-word** (`chat/streaming.py:33-44`). Nothing here assumes OpenAI. With slower local models this UX is acceptable but noticeably worse than real token streaming; optional later upgrade: PydanticAI streaming (text-first, validate at completion).

**OpenAI-specific behaviors to change:**
- `OpenAIChatModel`/`OpenAIProvider` construction (`agent.py:31-34`) → same classes with `base_url` (this *is* the provider abstraction).
- `OpenAIGroundingJudge` (`validator.py:66-98`) and the keyword extractor's `chat.completions.parse` (`keywords.py:255-263`) rely on OpenAI **structured outputs** (`response_format` json_schema). vLLM and recent Ollama both support json-schema `response_format`/`format`; keep the existing `GroundingJudge` Protocol, implement `OpenAICompatGroundingJudge` (same class renamed + configurable base_url), and add a tolerant JSON-parse fallback for servers without strict mode.
- `instructions.md` is SEC/English-specific ("internal SEC filing research assistant… Plain-English") → rewrite to language-neutral instructions that answer **in the language of the question** while keeping every grounding rule verbatim. Section "Corpus scope" must become config-driven rather than hard-coded filer list.

**Recommended provider story:** do **not** invent an `LLMProvider` interface — PydanticAI already is one, and the two direct-SDK call sites should be normalized onto the same "OpenAI-compatible endpoint + model name" settings block. Adding another hand-rolled abstraction would violate the repo's own dependency policy (`AGENTS.md`).

---

## 9. Persian Readiness Audit

### Backend
- **Unicode:** Python 3.12 strings are fine; all `Text` columns fine; JSONB fine.
- **Normalization:** none exists anywhere (the word "normalize" in `keywords.py:_normalize_terms` is dedup only). **Add `app/text/normalize.py`** (§6.2).
- **Tokenization assumptions:** `keywords.py` regexes are ASCII-only (defect listed above); tiktoken is Persian-tolerant but English-tuned.
- **Search:** see §6 — the single biggest gap.
- **Embeddings:** `text-embedding-3-small` is mediocre on Persian; BGE-M3 is a strict upgrade.
- **LLM prompts:** `instructions.md` English-only; `chat/streaming.py` fake streaming splits on `" "` (spaces) — works for Persian but `text.split(" ")` on ZWNJ-containing words is fine; note Persian text should ideally stream by grapheme/token, minor.
- **Output handling:** none problematic; markdown answer + JSON parts are Unicode-clean.
- **Server-side user-facing strings:** `app/assistant/status.py:19,35,38-46` and `chat/streaming.py:18-21` emit English status/failure text that the UI displays → needs i18n or bilingual copy when Persian UI lands.

### Frontend (`frontend/src/`)
- **RTL:** none. `index.html` has `lang="en"`, no `dir`; no `dir` attribute anywhere in app code (the only `rtl` matches are incidental Tailwind classes inside the shadcn `ui/sidebar.tsx` template). Layouts use physical properties (`text-left`, `pl-5`, `border-l-2`, `pr-3` in `AssistantMarkdown.tsx:14-22`, `SourcePassageSheet.tsx:24-31`) instead of logical properties (`ps-`, `pe-`, `text-start`) — RTL will need a systematic pass.
- **Persian typography:** `index.css:54` sets Geist Variable — **Geist has no Arabic-script glyphs**, so Persian would render in an arbitrary fallback. Add a Persian font (e.g. Vazirmatn) and a font stack that pairs it with Geist for Latin.
- **Mixed RTL/LTR:** citations like `AAPL · 10-K · 2024-03-15` (`lib/citations.ts:79-90`) and numbers inside Persian sentences will misplace bidi boundaries; needs `dir="auto"`/`<bdi>` handling in message bubbles, citation chips, and the source sheet; code blocks stay LTR (`ui/code-block.tsx`).
- **i18n:** none; strings hard-coded in `Login.tsx`, `SignUp.tsx`, `ChatEmptyPage.tsx`, `ChatLayout.tsx`, etc. Decide: bilingual UI (recommended, fa/en toggle) with a lightweight dictionary (this codebase's dependency policy favors a small hand-rolled `lib/i18n.ts` over react-i18next).
- **Markdown rendering:** `react-markdown` + `remark-gfm` are Unicode-clean; `withCitationLinks` regex `\[(\d+)\]` (`AssistantMarkdown.tsx:24-29`) works for Persian text with `[1]` markers (Persian-digit markers are a non-issue — instruct the model to emit ASCII digits in markers; validator regex `\[(\d+)\]` on the backend matches ASCII only, which is consistent).
- **Dates/numbers:** `filingDate` renders raw ISO (`citationLabel`, `citationHeader`) → format via `Intl.DateTimeFormat('fa-IR-u-ca-persian')` when Persian UI is on (Gregorian vs Jalali is a product decision, §24).

### Database
- **Encoding:** Supabase defaults to UTF8 — any local Postgres container must be created UTF8 (the official image defaults to UTF8 via `POSTGRES_INITDB_ARGS` only if locale set; in practice it is UTF8 by default in recent images — verify once).
- **Collation:** current queries never sort by Persian text (thread list sorts by `updated_at`), so ICU `fa` collation is optional; add `icu_fa` only if Persian-sorted lists are wanted later.
- **FTS:** the core problem — see §6.2. `search_vector` must move to a normalized representation.
- **Indexes:** HNSW/GIN unaffected by language; add pg_trgm GIN for `search_text`.

### PDF/OCR
- Nonexistent today. Persian-specific concerns once added: reading order in multi-column scanned docs (Docling's layout model helps; verify on real Persian scans), ZWNJ fidelity through OCR (Tesseract often drops or mangles ZWNJ — normalization must *rebuild* common ZWNJ joins), Persian digit recognition, mixed-direction lines. The citation page-number feature (`page` column → `p.{page}` in `format_passages_for_agent`) finally becomes meaningful with PDFs.

---

## 10. Local Deployment Audit

Current deployment shape: two Railway services (backend Dockerfile, frontend Dockerfile+Caddy), hosted Supabase, **no docker-compose** anywhere in the repo. `backend/Dockerfile` (python:3.12-slim + uv, uvicorn CMD), `frontend/Dockerfile` (pnpm build → caddy:2-alpine static serve with `try_files` SPA fallback and a `/health` endpoint), Caddyfile is minimal.

**Docker Compose is sufficient** for the target architecture. Proposed service graph:

```
frontend (caddy, static SPA)          → talks to backend over published port / reverse proxy
backend  (FastAPI + uvicorn)          → depends_on: postgres (healthy), ollama (healthy)
postgres  (pgvector/pgvector:pg16)    → volume pgdata; UTF8; healthcheck pg_isready
ollama   (or vLLM)  [LLM, Qwen]       → volume models; OpenAI-compatible at :11434/v1 (or :8000/v1)
tei        [embeddings: BAAI/bge-m3; optional reranker: bge-reranker-v2-m3]  → volume models; /v1/embeddings style API
docs-data volume (uploaded/original documents)
```

Evaluations:
- **CPU-only mode:** viable — Ollama running a quantized Qwen (e.g. `qwen3:8b` Q4) + TEI-CPU for BGE-M3 (1024-dim, fast on CPU); grounding-judge and keyword calls share the same LLM endpoint. Latency dominated by the agent loop (up to 20 requests/turn — consider lowering `request_limit` for local models).
- **GPU mode:** vLLM (stronger structured-output + tool-calling throughput, needs NVIDIA + WSL2 on Windows hosts) or Ollama with `nvidia` runtime; compose profiles (`cpu` / `gpu`) recommended.
- **Model serving:** keep `pydantic-ai`'s OpenAI-compatible client; no new client libraries.
- **Volumes/persistence:** pgdata (all product state), model cache, documents dir. Backend stays stateless (matches current design).
- **Startup dependencies:** `depends_on` with `condition: service_healthy` + healthchecks (pg_isready; `/health` for backend; `/api/tags` for Ollama; TEI `/health`). Run `alembic upgrade head` as backend entrypoint step or init container (existing Railway guide already does pre-deploy migration — mirror that in compose).
- **Networking:** single compose network; `ALLOWED_ORIGINS` must list the frontend origin; frontend `VITE_API_BASE_URL` is a **build-time** Vite env (both Dockerfiles bake env at build — for compose, pass build args or switch to runtime-injected config; minor decision).
- **Config:** all new settings through `app/config.py` (per repo rule; no scattered `os.getenv`).
- **Local auth:** the backend gains `/auth/signup`, `/auth/login`, `/auth/me`; JWT secret via `AUTH_SECRET`; no extra service needed.

---

## 11. Frontend Audit

Structure (all under `frontend/src/`):
- **Routing:** `App.tsx` — `/login`, `/signup`, protected `/chats` (+ `:threadId`).
- **Auth:** `lib/supabase.ts`, `hooks/useSession.ts`, `components/ProtectedRoute.tsx`, `PublicRoute.tsx`, `pages/Login.tsx`, `SignUp.tsx`, `components/chat/UserMenu.tsx` (`supabase.auth.signOut()`).
- **API/transport:** `lib/http.ts` (typed fetch + timeout + ApiError), `lib/api.ts` (Bearer injection via Supabase session), `lib/chat.ts` (threads/messages/citation-context calls), `hooks/useChatTransport.ts` (AI SDK `DefaultChatTransport` → `POST /chat/stream`, tees the SSE to extract `data-status` pipeline events).
- **Chat UI:** `components/chat/` — `ChatLayout`, `MessageList`, `MessageBubble`, `AssistantMessage`, `AssistantMarkdown` (converts `[n]` → citation buttons), `CitationMarker`, `CitationChip`, `SourcePassageSheet` (fetches surrounding chunks + renders tables), `PipelineStatus`, `ChatInput`, `ThreadSidebar`, `ThreadsProvider`, `ChatError`.
- **State:** `contexts/threads-context.ts`, `hooks/useThreads.ts` (Supabase-free already — they call FastAPI).
- **Rendering deps:** `ai@^5` + `@ai-sdk/react@^2` (message model, transport), `react-markdown`, `remark-gfm`, `shiki` code highlighting, Tailwind 4 + shadcn UI kit.

Assessment:
- **Keep almost everything.** The frontend is already decoupled from OpenAI and from the database; its only Supabase touchpoints are auth (7 files, listed in §5) and none of the chat logic.
- The AI SDK wire format (`UIMessage`, `text-delta`, `data-citation`, `data-status`) is produced by `app/chat/streaming.py` and consumed by AI SDK primitives — **preserve this contract** through the migration so the chat layer is untouched.
- Refactor needs: i18n layer, RTL/logical CSS pass, Persian font stack, bidi-safe citation/date formatting, runtime-injected API base URL for compose (build-time VITE_* is awkward with docker compose).
- No tests exist on the frontend (only `pnpm lint` / `pnpm build`); the AI-SDK interaction is covered indirectly by backend SSE tests (`tests/chat/test_streaming.py`).

---

## 12. Database and Migration Audit

Schema (Alembic head `d2e4b7a9c1f3`; models in `backend/app/database/models/`):

| Table | Model | Notes for migration |
| --- | --- | --- |
| `users` | `user.py` | `id` = Supabase `auth.users.id` (docstring) → becomes plain locally-issued UUID; needs `password_hash` (+ optional `created_at` already via mixin) |
| `source_documents` | `source_document.py` | SEC-shaped columns (`ticker` NOT NULL, `cik` NOT NULL, `form`, `accession_number` NOT NULL UNIQUE, `source_url` NOT NULL) — **schema is SEC-specific**: arbitrary Persian documents have none of these. Recommend: keep table, make SEC columns nullable, add `title`, `language`, `source_format`, `file_path` (see §18) |
| `document_chunks` | `document_chunk.py` | `Vector(1536)` via `EMBEDDING_DIMENSIONS`; `search_vector` generated tsvector('english') exists only in migration SQL (not in the model — intentional, commented at `document_chunk.py:23-26`); `chunk_metadata` JSONB; FK CASCADE to document |
| `document_tables` | `document_table.py` | SEC table mirror; harmless for other formats (may stay empty) |
| `chat_threads` / `chat_messages` / `message_citations` | `chat_thread.py`, `chat_message.py`, `message_citation.py` | Provider-neutral; `message_citations.chunk_id` FK is `ON DELETE RESTRICT` (protects cited chunks from re-index deletion — `_delete_chunks` handles it explicitly) |

Migration infrastructure: Alembic + `alembic/env.py` importing `Base.metadata`; `DATABASE_URL` via settings (`sqlalchemy_database_url` normalizes to `postgresql+psycopg://`). Nothing Supabase-specific in Alembic itself — pointing `DATABASE_URL` at local Postgres just works.

Supabase-specific SQL to remove/replace in a **new** migration (never rewrite history): RLS policies + `auth.uid()` references (§5.7). The `authenticated` role won't exist on a vanilla local cluster (Supabase creates it), so leaving the policies in place for fresh local installs would actually fail — dropping them is required, not optional.

---

## 13. Testing Audit

Current suite (`backend/tests/`, pytest, `pythonpath=["."]`, marker `integration` = "requires live Supabase and OpenAI credentials"):

| Area | Files | Fate after migration |
| --- | --- | --- |
| Retrieval unit | `tests/retrieval/test_fusion.py`, `test_types.py`, `test_queries.py`, `test_retriever.py` | **Keep**; `test_queries.py` asserts SQL shape incl. fts-config interpolation → update for new search representation; `test_retriever.py` patches provider boundaries → survives unchanged if the same function names stay |
| Keywords | `tests/retrieval/test_keywords.py` (116 lines, English heuristics) | **Replace** with Persian normalizer/keyword tests |
| Ingest | `tests/ingest/test_chunking.py`, `test_chunk_and_embed.py`, `test_sec_tables.py` | Keep (HTML/SEC path retained); add PDF/OCR tests separately |
| Chat | `tests/chat/test_messages.py`, `test_streaming.py`, `test_orchestrator.py`, `test_routes.py`, `test_ownership.py`, `test_persistence.py` | **Keep nearly all** — they mock `append_grounded_turn`/route deps, no Supabase imports; `test_routes.py`/`test_ownership.py` patch auth deps → survive local JWT (same dependency names) |
| Grounding | `tests/grounding/test_validator.py` (FakeGroundingJudge) | **Keep** — validator logic unchanged |
| Assistant | `tests/assistant/test_outputs.py`, `test_tools.py` | **Keep** (tools test against patched DB/session helpers) |
| Integration (marked, skipped by default) | `tests/retrieval/test_retriever_integration.py`, `tests/assistant/test_agent_integration.py` | **Refactor**: repoint marker at "requires live local services" (docker pg + local models) — they are excellent end-to-end acceptance tests |

Strengths worth preserving: the fast suite hits **no network and no DB** (repo rule in `backend/AGENTS.md`); provider boundaries are the patch points, which is exactly what makes the provider swap testable.

**New tests to add (design only, do not write yet):**
1. `tests/text/test_normalize.py` — ي/ی, ك/ک, ZWNJ variants, digit families, diacritics, punctuation, mixed scripts; idempotence; original-text preservation.
2. `tests/retrieval/test_persian_fts.py` (integration) — normalized ingest then retrieve by Persian query with ZWNJ/Arabic-codepoint variants → must match; English-in-Persian query test.
3. `tests/retrieval/test_reranker.py` — fake reranker reorders fused results; disabled-by-default behavior.
4. `tests/providers/test_embedding_provider.py` / `test_llm_provider.py` — fake OpenAI-compatible servers (respx/httpx MockTransport) verifying base_url wiring, dim checks, batch behavior.
5. `tests/auth/test_local_auth.py` — signup/login/verify, expired/garbage tokens, `CurrentUser` parity with old Supabase path.
6. `tests/ingest/test_pdf.py` — digital PDF fixture (Persian text layer) → chunks with page numbers; scanned fixture behind an OCR marker.
7. `tests/grounding/test_persian_citation.py` — validator behavior with Persian excerpts (verbatim matching incl. ZWNJ-sensitive excerpt comparisons).
8. End-to-end: `tests/e2e/test_rag_local.py` (integration) — compose-based pg + fake LLM answering a scripted Persian question; asserts citations persisted and streamed parts.

---

## 14. Keep / Replace / Refactor / Add Matrix

| Area | Current implementation (actual paths) | Decision | Reason |
| --- | --- | --- | --- |
| Frontend chat layer | `frontend/src/components/chat/*`, `hooks/useChatTransport.ts`, `lib/chat.ts`, `lib/http.ts`, AI SDK v5 | **KEEP** | Provider/DB-agnostic; contract with backend (`app/chat/streaming.py`) is clean |
| Frontend auth | `lib/supabase.ts`, `hooks/useSession.ts`, `pages/Login.tsx`, `SignUp.tsx`, `components/ProtectedRoute.tsx`, `PublicRoute.tsx`, `chat/UserMenu.tsx` | **REFACTOR** | Swap Supabase client for local token store + `/auth` API; UI components stay |
| Frontend i18n/RTL | `index.html`, `index.css`, all components | **ADD/REFACTOR** | No RTL, no Persian font (Geist), no i18n; hard-coded English strings |
| Retrieval engine | `app/retrieval/retriever.py`, `fusion.py`, `queries.py` | **KEEP/REFACTOR** | Hybrid+RRF is sound; queries gain normalized `search_text`, optional reranker hook |
| Embeddings | `app/retrieval/embeddings.py`, `ingest/embeddings.py` | **REPLACE** (behind new `EmbeddingProvider`) | OpenAI `text-embedding-3-small` @1536 → BGE-M3 @1024; drop `dimensions=` kwarg |
| FTS keyword extraction | `app/retrieval/keywords.py` | **REPLACE** | ASCII-only regexes; English stopword lists; LLM structured-output dependency; broken for Persian by construction |
| OpenAI LLM | `app/assistant/agent.py` | **REPLACE config, KEEP framework** | PydanticAI + OpenAI-compatible base_url → local Qwen (Ollama/vLLM) |
| Grounding judge | `app/grounding/validator.py:OpenAIGroundingJudge` | **REFACTOR** | Keep `GroundingJudge` Protocol + all fail-closed rules; retarget to local endpoint + JSON fallback |
| Grounding rules | `TurnRegistry`, `validate()`, orchestrator retry | **KEEP** | The product's trust contract |
| Streaming | `app/chat/streaming.py` | **KEEP** (later optionally upgrade to real token streaming) | Already provider-agnostic; fake streaming is fine initially |
| Supabase DB access (chats/users) | `app/database/supabase.py`, `chats.py`, `users.py`, route wiring in `api/chat.py` | **REPLACE** | Port to SQLAlchemy; `require_thread_access` ownership check preserved |
| Supabase Auth | `app/auth/dependencies.py` | **REPLACE** | Local JWT; keep `get_current_user`/`get_access_token` signatures |
| RLS policies | `alembic/versions/3c81ca3fef26` (`_enable_rls_and_policies`), `b7f4a1c2d9e8` | **REPLACE** (drop) | `auth.uid()`/`authenticated` don't exist locally; Python checks remain |
| Postgres + pgvector | `app/database/session.py`, `models/document_chunk.py`, migrations | **KEEP** | Already plain Postgres; point at local instance |
| Schema (SEC columns) | `models/source_document.py` | **REFACTOR** | Make SEC metadata nullable; add `title`, `language`, `source_format`, `file_path`, `search_text` on chunks |
| Ingestion chunker | `ingest/chunking.py` (Docling HybridChunker, 512 tokens) | **KEEP/REFACTOR** | Mechanics fine; add normalization step, format dispatch (PDF/DOCX), configurable tokenizer |
| SEC table extractor | `ingest/sec_tables.py` | **KEEP** (legacy corpus) | SEC-specific but harmless; new formats use generic Docling tables |
| PDF/OCR | — | **ADD** | Docling pipelines (`do_ocr`, `fas` lang); OCR quality gates |
| Upload/storage | — | **ADD** | Upload API + local documents dir/volume; no Supabase Storage existed |
| Citations & source viewer | `api/chat.py:citation_context_response`, `SourcePassageSheet`, `citationChip` | **KEEP/IMPROVE** | Improve with real PDF page refs; verbatim-excerpt rule unchanged |
| Deploy | `backend/Dockerfile`, `frontend/Dockerfile`, `Caddyfile`, `docs/guides/railway-deployment.md` | **REFACTOR** | Add docker-compose (pg, backend, frontend, llm, tei), local deployment guide; Railway docs become optional |
| Config | `app/config.py`, `.env.example`s | **REFACTOR** | Provider-neutral `llm_*`/`embedding_*`/`rerank_*`/`auth_*` settings; keep fail-fast rule |
| Tests | `backend/tests/*` | **KEEP + ADD** | See §13 |

---

## 15. Target Local-Persian Architecture

### 15.1 Architecture

```
Browser (React SPA, fa/en, RTL-aware)
   │  Bearer JWT (local auth)        AI SDK v5 transport (unchanged wire format)
   ▼
FastAPI (backend/app)
   ├─ api/auth.py        /auth/signup /auth/login /me        (NEW: local JWT, argon2/scrypt hash)
   ├─ api/chat.py        unchanged routes, Session instead of Supabase client
   ├─ chat/orchestrator.py  unchanged turn lifecycle
   ├─ assistant/agent.py    PydanticAI Agent → OpenAI-compatible base_url (Ollama|vLLM)
   │     └─ tools.py → DocumentRetriever
   ├─ retrieval/  retriever → [EmbeddingProvider] + [Persian normalizer → FTS keywords]
   │              → pgvector semantic ∥ tsvector('simple', search_text)+trgm lexical
   │              → RRF → [RerankerProvider: bge-reranker-v2-m3] → hydrate
   ├─ grounding/validator.py  unchanged rules; judge via OpenAI-compatible endpoint
   └─ database/session.py  SQLAlchemy/psycopg  →  PostgreSQL 16 + pgvector (docker volume)
                                                     ▲
Ingestion CLI + upload API ─────────────────────────┘
   PDF/DOCX/HTML → Docling (+OCR fas) → normalize → search_text → chunk → EmbeddingProvider → DB
   originals → local filesystem (docs-data volume)

Sidecar services: ollama|vLLM (Qwen), TEI (bge-m3, bge-reranker-v2-m3)
```

### 15.2 Provider abstractions — explicit decision

| Abstraction | Verdict | Why / Where / Consumers |
| --- | --- | --- |
| `EmbeddingProvider` | **YES — introduce** | Two call sites today with duplicated OpenAI code (`app/retrieval/embeddings.py`, `ingest/embeddings.py`) and a hard dim contract. One small protocol: `embed_documents(texts) -> list[list[float]]`, `embed_query(text) -> list[float]`, `dimensions` property. Location: `backend/app/providers/embedding.py` with an OpenAI-compatible implementation (covers OpenAI, Ollama, TEI, vLLM, infinity). Consumers: `retrieval/retriever.py:embed_query` import, `ingest/chunk_and_embed.py:embed_texts` import. Unit-tested with a fake; the current fast tests keep passing because they patch these symbols. |
| `RerankerProvider` | **YES — introduce (small, optional)** | No reranker exists; Persian lexical ranking is the weakest leg, so reranking carries real value. Protocol: `rerank(query, passages: list[RetrievedPassage], top_k) -> list[RetrievedPassage]` with a pass-through default implementation. Location: `backend/app/providers/reranker.py`; wired in `DocumentRetriever._search_with_session` after RRF truncation. Config flag `RETRIEVAL_RERANK_ENABLED=false` default. |
| `LLMProvider` | **NO — do not introduce** | PydanticAI *is* the LLM abstraction (`Agent` + model classes accept any OpenAI-compatible provider). The repo's own dependency policy (`AGENTS.md`: "frameworks where a function would do", no wrappers over existing deps) argues against a second layer. Change = settings + `agent.py:31-34` construction. |
| `StorageProvider` | **NO — do not introduce (yet)** | There is no object storage anywhere; a single `documents` directory setting + small `app/storage/local.py` path helpers (if even needed) satisfies the requirement. Revisit only if S3-compatible backends become a requirement. |
| `AuthProvider` | **NO — replace, don't abstract** | Dual-mode auth (Supabase *and* local) is not a stated goal; keeping a dead Supabase path behind a protocol would violate the no-backwards-compat-shims rule. Replace `app/auth/dependencies.py` internals with local JWT verification while keeping the public dependency functions (`get_current_user`, `get_access_token`) so no route or test changes. The `GroundingJudge` Protocol (`grounding/validator.py:59-63`) already exists — that's the one place an interface is already justified and stays. |

### 15.3 Model strategy (evaluation of the proposed direction)

- **Qwen via Ollama or vLLM — appropriate.** Qwen2.5/Qwen3 are top-tier open models for Persian and tool-calling; both servers expose OpenAI-compatible APIs that PydanticAI consumes unchanged. vLLM preferred when a GPU exists (better structured-output/tool throughput, higher concurrency); Ollama preferred for simplicity/CPU. Constrain `openai_agent_request_limit` (config) for local latency; temperature 0 already set.
- **BAAI/bge-m3 — appropriate and the single biggest retrieval win.** Strong Persian retrieval, 1024 dims, 8192-token context (fits the 512-token chunks with huge margin). Serve via TEI/Ollama/infinity. Cost: dimension migration + one-time re-embed (§12).
- **Reranker — appropriate, and needed.** bge-reranker-v2-m3 multilingual cross-encoder; without English-style stemming on the FTS leg, fusion quality for Persian will lean heavily on the dense leg; a cross-encoder over the fused pool is the cleanest compensation. Keep optional and behind the provider.
- **Local Postgres + pgvector — appropriate, near-zero migration risk.** The code already speaks plain Postgres.
- **Local OCR — appropriate with expectations set.** Docling + Tesseract `fas` is the lowest-friction path (no new framework); quality on real-world scans is the main risk (§20). EasyOCR (`fa`) is the in-Docling alternative worth benchmarking.
- **One correction to the proposed direction:** the lexical leg is not "make FTS Persian" — PostgreSQL has no Persian configuration. The plan must fund the normalizer + `simple`-config tsvector + trgm work (§6.2, §18) or Persian keyword search simply will not function.

---

## 16. Proposed Directory Changes

All additive except where marked (no renames of existing modules):

```text
backend/app/
├── providers/                    # NEW
│   ├── __init__.py
│   ├── embedding.py              # EmbeddingProvider protocol + OpenAI-compatible impl (bge-m3 via TEI/Ollama)
│   └── reranker.py               # RerankerProvider protocol + pass-through + TEI /rerank impl
├── text/                         # NEW — Persian normalization core
│   ├── __init__.py
│   ├── normalize.py              # normalize(), ZWNJ/codepoint/digit/diacritic handling (shared ingest+query)
│   └── stopwords.py              # Persian stopword list (data-backed, small)
├── auth/
│   ├── dependencies.py           # MODIFIED: local JWT verification (same function signatures)
│   └── local.py                  # NEW: signup/login, password hashing, token issue/verify
├── api/
│   ├── auth.py                   # MODIFIED: + /auth/signup, /auth/login
│   └── chat.py                   # MODIFIED: Supabase client → SQLAlchemy session
├── database/
│   ├── supabase.py               # DELETE (after chats/users ported)
│   ├── chats.py                  # REWRITE internals: PostgREST → SQLAlchemy
│   ├── users.py                  # REWRITE: local user insert
│   └── models/source_document.py # MODIFIED: nullable SEC cols + title/language/source_format/file_path
├── ingest/ (or new backend/ingest/formats/)
│   ├── formats.py                # NEW: format dispatch html|pdf|docx, OCR pipeline options
└── storage/
    └── local.py                  # NEW: documents dir resolution (tiny)
frontend/src/
├── lib/i18n.ts                   # NEW: fa/en dictionaries (hand-rolled per repo policy)
├── lib/auth.ts                   # NEW: token store replacing lib/supabase.ts
├── hooks/useSession.ts           # MODIFIED: local session
└── (RTL/i18n passes across components/chat/*, pages/*)
docker-compose.yml                # NEW (repo root) + docker/ env files
docs/local-deployment.md          # NEW (replaces railway/supabase guides as primary)
```

---

## 17. Proposed Configuration Changes

`backend/app/config.py` — replace the `openai_*` block and Supabase fields with (names indicative; keep fail-fast):

```python
# LLM (OpenAI-compatible; Ollama: http://ollama:11434/v1, vLLM: http://vllm:8000/v1)
llm_base_url: str                      # required
llm_api_key: str = "not-needed"        # Ollama ignores; vLLM may require
llm_model: str = "qwen3:8b"
llm_agent_request_limit: int = 12      # lowered default for local latency
llm_agent_temperature: float = 0.0
# Embeddings
embedding_base_url: str                # required (TEI/Ollama)
embedding_model: str = "bge-m3"
embedding_dimensions: int = 1024       # feeds EMBEDDING_DIMENSIONS + migration
embedding_batch_size: int = 32
# Reranker (optional)
rerank_enabled: bool = False
rerank_base_url: str | None = None
rerank_model: str = "bge-reranker-v2-m3"
# Retrieval / FTS
retrieval_fts_config: str = "simple"   # was "english"; lexemes come from our normalizer
retrieval_fts_keyword_model: str = ""  # now optional (defaults to llm_model) — Persian path is deterministic
# Auth
auth_secret: str                       # required, fail fast
auth_token_ttl_minutes: int = 10080
# DB / server
database_url: str                      # now local postgres
allowed_origins: str = "http://localhost:5173"
```

Frontend (`frontend/src/lib/env.ts`): `VITE_API_BASE_URL` stays; `VITE_SUPABASE_URL`/`VITE_SUPABASE_ANON_KEY` removed; add `VITE_DEFAULT_LOCALE` (fa|en). Note the build-time-vs-runtime env caveat for compose (§10).

Hard-coded model references to sweep: `config.py` defaults (`gpt-5.5`, `gpt-4.1-mini` ×3), `constants.py:2`, `.env.example`s, `assistant/status.py` (log line prints model name only), `scripts/smoke_assistant.py:22` (`print(Model: settings.openai_chat_model)`), and `instructions.md` corpus section.

---

## 18. Proposed Database Changes

Single forward migration set on top of head `d2e4b7a9c1f3` (never editing existing revisions):

1. **Embedding dimension** — `ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(1024)` (requires dropping `ix_document_chunks_embedding_hnsw` first, re-creating after); all rows must be re-embedded before search works (deployment step, not migration step — migration can leave rows NULL/invalid; retriever already filters `embedding IS NOT NULL`).
2. **Search representation** —
   ```sql
   ALTER TABLE document_chunks ADD COLUMN search_text text;
   UPDATE ... -- backfilled by re-ingest or an app-side normalization script
   ALTER TABLE document_chunks DROP COLUMN search_vector;   -- old generated ('english')
   ALTER TABLE document_chunks
     ADD COLUMN search_vector tsvector
     GENERATED ALWAYS AS (to_tsvector('simple', coalesce(search_text, text))) STORED;
   CREATE INDEX ix_document_chunks_search_vector_gin ... ;  -- recreate
   CREATE INDEX ix_document_chunks_search_text_trgm ON document_chunks USING gin (search_text gin_trgm_ops);
   CREATE EXTENSION IF NOT EXISTS pg_trgm;
   ```
   (`queries.py:full_text_search` needs no SQL change beyond the config switch — it reads `settings.retrieval_fts_config`.)
3. **Users** — `ALTER TABLE users ADD COLUMN password_hash text;` (nullable transitionally; enforced once local auth is live). Drop all RLS policies + `DISABLE ROW LEVEL SECURITY` for all 7 tables (Supabase roles don't exist locally).
4. **Documents** — `ALTER TABLE source_documents ALTER COLUMN ticker DROP NOT NULL; ... cik, form, filing_date, accession_number, primary_document, source_url` become nullable (or `accession_number` gets a generated fallback); `ADD COLUMN title text, language text, source_format text, file_path text` with a partial unique index on `file_path` if dedupe is wanted.
5. Optional: `chat_threads.title` stays String(255) — fine; consider `Text` for long Persian titles.
6. `document_chunks.chunk_metadata` stays JSONB — new-format metadata (ocr engine, page count, language) drops in without schema change.

**What must NOT change:** `message_citations` (contract with the frontend), `chat_messages.parts` JSONB wire format, chunk `text` column semantics (verbatim original — excerpts must stay verbatim for the validator and source viewer).

---

## 19. Proposed Model Strategy

(Consolidated; details in §15.3.)

| Role | Model | Serving | Notes |
| --- | --- | --- | --- |
| Chat/agent LLM | Qwen3 8B (GPU) / Qwen3 4B or Qwen2.5 7B-instruct quantized (CPU) | Ollama (`/v1`) or vLLM (`/v1`) | Must support tool calling + JSON-schema output for GroundedAnswer; temperature 0 |
| Grounding judge | Same endpoint, smaller model if GPU-bound (e.g. Qwen3 4B) | same | Judge prompt already language-agnostic; keep `GroundingJudge` Protocol |
| FTS keywords | Deterministic Persian normalizer path; optional LLM refinement | same endpoint | `keywords.py` replaced for Persian; fast path stays |
| Embeddings | BAAI/bge-m3 (dense) | TEI or Ollama | 1024 dims; batch 32 default |
| Reranker (optional) | BAAI/bge-reranker-v2-m3 | TEI `/rerank` | Disabled by default flag |
| Chunk tokenizer | tiktoken `cl100k_base` retained as heuristic OR HF tokenizer of bge-m3 | in-process | Non-blocking decision; consistent counting is what matters |
| OCR | Tesseract `fas` via Docling (baseline), EasyOCR `fa` (alternative) | in-process | Benchmark on real scans; normalization repairs ZWNJ afterwards |

All models are swappable via config only — that is the acceptance criterion for "provider-agnostic".

---

## 20. Risk Register

| # | Risk | Impact | Likelihood | Mitigation |
| --- | --- | --- | --- | --- |
| R1 | Local LLM produces weaker structured output / worse `[n]`+verbatim-excerpt discipline than GPT-class models → more grounding-failure turns | Product trust breaks (fail-closed errors surface to users) | Medium-High | Prefer larger Qwen tiers; keep temperature 0; keep 2-attempt retry; add citation-contract prompt tests; consider relaxing validator from "verbatim substring" to normalized-substring check (careful: preserves trust) |
| R2 | Structured-output (`response_format` json_schema) support varies across Ollama/vLLM versions → judge/keyword calls fail | Validation errors | Medium | Feature-detect; JSON-parse fallback path behind `GroundingJudge` Protocol; pin server versions in compose |
| R3 | Postgres has no Persian FTS config — lexical leg underperforms even after normalization (no stemming) | Recall gap vs English baseline | High | pg_trgm + reranker compensate; conservative suffix folding; measure with a Persian golden-question set before/after |
| R4 | Persian OCR quality (Tesseract `fas`) on real scanned documents is poor | Bad chunks → wrong citations | Medium-High | OCR confidence gates; benchmark EasyOCR `fa`; preprocessing (deskew/binarize); route hopeless scans to manual review; normalization repairs ZWNJ |
| R5 | Dimension migration + re-embed on CPU takes hours for large corpora | Deployment friction | Low-Medium | Corpus is small now; batch + persist vectors incrementally; embeddings cache by text hash |
| R6 | ZWNJ policy mistakes (normalize too aggressively / not enough) silently hurt both embedding and FTS | Subtle recall loss | Medium | Golden test set; keep original `text` untouched for display; normalizer unit tests are mandatory (§13.1) |
| R7 | Agent loop latency on local models (up to 20 requests/turn) | UX degradation | High | Lower request limit; real token streaming (later phase); status pipeline already communicates progress |
| R8 | Frontend RTL/i18n regressions in citation chips/source sheet (bidi, mixed numerals) | UI correctness | Medium | `dir="auto"`+`<bdi>`; visual checklist per component; browser-use GUI testing pass |
| R9 | Build-time Vite env conflicts with compose deployment | Deployment friction | Low | Runtime config injection or compose build args |
| R10 | Scope creep into the SEC corpus path while adding Persian formats | Regression risk | Medium | Keep `ingest/sec_tables.py` + HTML path frozen behind the format dispatcher; new tests before refactor |

---

## 21. Migration Phases

**Phase 0 — Local foundation (no behavior change).** docker-compose with `postgres/pgvector` + backend + frontend; `DATABASE_URL` → local PG; run existing migrations; drop-and-recreate RLS in a new migration; prove `smoke_retrieval.py` (with OpenAI still) against local Postgres. *Exit: existing fast tests + one integration test green on local PG.*

**Phase 1 — Supabase removal (auth + persistence).** Local auth (`/auth/signup|login`, JWT verify in `auth/dependencies.py`), port `database/chats.py` + `users.py` to SQLAlchemy, delete `database/supabase.py`, frontend token store + `useSession` swap. *Exit: repo has zero `supabase` imports; all chat tests green.*

**Phase 2 — Embedding provider + BGE-M3.** Introduce `providers/embedding.py`; config block; dimension migration; re-embed; adjust `embed_*` dim checks (remove `dimensions=` kwarg). *Exit: retrieval smoke test with local embeddings; fast tests green.*

**Phase 3 — LLM provider (local inference).** `llm_base_url` settings; `agent.py` model construction; judge + keyword extractor retargeted with JSON fallback; verify tool-calling + structured `GroundedAnswer` end-to-end; tune `request_limit`. *Exit: `smoke_assistant.py` green against local Qwen; `tests/assistant/test_agent_integration.py` (repointed) passes.*

**Phase 4 — Persian text pipeline.** `app/text/normalize.py` + stopword list; `search_text` column + tsvector(`simple`) + trgm migration; query-side normalization in retriever; rewrite `keywords.py` Persian-first (LLM refinement optional); bilingual `instructions.md` ("answer in the question's language"); validator excerpt checks stay verbatim-on-original. *Exit: Persian golden-question retrieval suite passes; mixed fa/en queries work.*

**Phase 5 — Ingestion upgrade (PDF/DOCX/OCR + upload).** Format dispatcher; Docling PDF/OCR options; `source_documents` columns; upload API + local storage dir; re-chunk tooling; OCR quality gates. *Exit: a Persian digital PDF and a scanned PDF ingest with page-accurate citations.*

**Phase 6 — Reranker + streaming (optional quality/UX).** `providers/reranker.py` + retriever hook + flag; (optional) real token streaming via PydanticAI streaming with validation-on-completion. *Exit: A/B recall improvement on the golden set; streaming first-token < ~2s.*

**Phase 7 — Frontend Persian/RTL + i18n.** `lib/i18n.ts`, RTL pass, Vazirmatn font stack, bidi-safe citations/dates, bilingual server status strings (or client-side mapping of status stages). *Exit: full fa UI walkthrough incl. citation sheet and tables.*

**Phase 8 — Deployment hardening.** Compose profiles cpu/gpu, healthchecks, volumes, migration-on-start, docs (`docs/local-deployment.md`), backup/restore notes, env templates. *Exit: one-command bring-up on a clean machine.*

## 22. Recommended Implementation Order

**0 → 1 → 2 → 3 → 4 → 5 → 7 → 6 → 8** (i.e., Persian UI before the optional reranker/streaming phase; deployment hardening last). Rationale: Supabase removal (Phase 1) unlocks everything else and is the least risky big move; embeddings (2) and LLM (3) are independent of language work; the Persian pipeline (4) is the highest-value/highest-effort phase and benefits from landing after providers so the golden-question suite can run fully local; UI (7) can proceed in parallel with 5 once the API is stable; reranker (6) is deferred until Persian retrieval can be measured without it (so its contribution is attributable).

## 23. Estimated Complexity per Phase

| Phase | Size | Main cost drivers | Riskiest item |
| --- | --- | --- | --- |
| 0 Local foundation | S-M | compose files, RLS-drop migration | pgvector image/locale |
| 1 Supabase removal | M | chats.py port, frontend auth swap, 7 files frontend | JWT/token-storage decisions |
| 2 Embedding provider | S-M | provider module, migration, re-embed run | dim mismatch bugs |
| 3 LLM provider | S-M | config + 3 call sites; fallback JSON path | structured-output compat (R2) |
| 4 Persian pipeline | **L** | normalizer, migration, keyword rewrite, golden set | R3/R6 (recall, ZWNJ) |
| 5 Ingestion upgrade | **L** | format dispatch, OCR, upload API, columns | OCR quality (R4) |
| 6 Reranker/streaming | M | provider + hook; streaming redesign | validator/stream interaction |
| 7 Frontend fa/RTL | M-L | i18n, logical CSS, bidi edge cases | citation sheet bidi (R8) |
| 8 Deployment hardening | S | profiles, docs, healthchecks | Windows/WSL2 GPU quirks |

## 24. Open Questions / Decisions That Must Be Made Before Coding

1. **Single-user or multi-user local?** If truly personal/single-operator, auth could collapse to a single configured account or even token-less operation — this changes Phase 1's scope materially (and the `users` FK story). Recommended default: keep multi-user-capable local auth (cheap, preserves all ownership code).
2. **Auth token mechanics:** stateless JWT in localStorage vs httpOnly cookie (XSS posture) — and stdlib HMAC token vs adding `pyjwt` (repo dep policy pushes toward a tiny hand-rolled token or PyJWT with justification).
3. **Ollama vs vLLM** (and target hardware: GPU present? Windows host → WSL2 for GPU): determines compose profiles and default model tags. Can be deferred — config accepts both.
4. **Which Qwen generation/size** is the baseline (Qwen3 8B vs Qwen2.5 14B/32B if GPU allows) — affects grounding quality (R1) and Phase 3 acceptance numbers.
5. **ZWNJ / normalization policy** (exact spec): keep ZWNJ in embedding input? FTS-side ZWNJ→space? Suffix folding (ها/تر/ترین) on or off? Must be frozen before writing `normalize.py` (R6) — decide with a small labeled query/document set.
6. **Persian FTS stopword list source** (hand-curated vs published list) and whether the LLM keyword-refinement step survives at all for Persian.
7. **Corpus reality check:** what fraction of target Persian documents are **scanned** PDFs (drives OCR priority/Phase 5 effort), and what are the document types (contracts? financial statements? academic papers?) — also determines whether the SEC-shaped `source_documents` columns or a generic metadata JSONB wins.
8. **UI language model:** Persian-first RTL with optional English, or bilingual toggle? Gregorian or Jalali dates for `filingDate`? Affects i18n scope and date formatting.
9. **Excerpt matching rule under normalization:** should the grounding validator keep strict verbatim matching against original `text` (recommended — preserves trust), or accept normalized equivalence? Any relaxation must be an explicit, tested decision.
10. **Legacy SEC corpus:** keep the existing SEC ingestion path working alongside Persian documents (recommended: yes, behind the format dispatcher), or migrate the product fully to the Persian corpus and let SEC code atrophy?
11. **Real token streaming:** commit now (Phase 6) or accept fake streaming for v1? Local-model latency suggests committing if GPU hardware is confirmed.
12. **Migration of existing data:** is anything in the hosted Supabase project worth exporting (threads/messages/citations), or does local start clean? (Schema is small; a one-off export script is cheap but must be decided before dropping Supabase access.)

---

### Appendix A — Exact OpenAI call-site inventory

| File:Line | Call |
| --- | --- |
| `backend/app/assistant/agent.py:31-34` | `OpenAIChatModel(settings.openai_chat_model, provider=OpenAIProvider(api_key=settings.openai_api_key))` |
| `backend/app/grounding/validator.py:67-68` | `OpenAI(api_key=settings.openai_api_key)` |
| `backend/app/grounding/validator.py:80-94` | `chat.completions.parse(model=settings.openai_grounding_model, response_format=CitationGroundingDecisionList)` |
| `backend/app/retrieval/embeddings.py:15-19` | `embeddings.create(model=settings.openai_embedding_model, dimensions=settings.openai_embedding_dimensions)` |
| `backend/app/retrieval/keywords.py:111-112` | `OpenAI(api_key=settings.openai_api_key)` |
| `backend/app/retrieval/keywords.py:255-263` | `chat.completions.parse(model=settings.retrieval_fts_keyword_model, response_format=FtsKeywordExtraction)` |
| `backend/ingest/embeddings.py:25-29` | `embeddings.create(model=..., dimensions=...)` batch loop |
| `backend/ingest/chunking.py:20,34-44,92` | tiktoken `cl100k_base` via docling `OpenAITokenizer` |
| `backend/app/config.py:21-27`, `backend/.env.example:18-26` | settings/env |
| `backend/pyproject.toml:13`, `backend/uv.lock` | `openai==2.38.0` dependency |

### Appendix B — Exact Supabase call-site inventory

| File | Usage |
| --- | --- |
| `backend/app/auth/dependencies.py:10-12,49-62` | `acreate_client` + `auth.get_user(jwt)` |
| `backend/app/database/supabase.py` | `get_service_role_client`, `create_user_client` |
| `backend/app/database/users.py` | service-role upsert into `users` |
| `backend/app/database/chats.py` | all thread/message/citation persistence (PostgREST) |
| `backend/app/chat/orchestrator.py:9` + `app/chat/streaming.py:9` | `AsyncClient` type hints only |
| `backend/app/api/chat.py:25,115-192` | `create_user_client` in 5 handlers |
| `backend/alembic/versions/3c81ca3fef26_initial_schema.py:276-488`, `b7f4a1c2d9e8:60-69` | RLS + `auth.uid()` policies |
| `backend/app/config.py:16-18`, `backend/.env.example:4-8` | `SUPABASE_*` settings |
| `frontend/src/lib/supabase.ts`, `lib/env.ts:12`, `lib/api.ts:4-7`, `hooks/useSession.ts`, `pages/Login.tsx:22`, `pages/SignUp.tsx`, `components/chat/UserMenu.tsx:20,34` | browser auth |
| `frontend/Dockerfile:14-16`, `frontend/.env.example` | build args |
| `docs/guides/supabase-setup.md`, `docs/guides/railway-deployment.md`, `docs/architecture.md` | documentation |
