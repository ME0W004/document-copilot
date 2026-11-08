# Sprint 2 Report — Persian-Aware Retrieval

**Date:** 2026-09-10
**Branch context:** `development` (workspace is a content-verified snapshot; no git metadata — see `docs/baseline.md` §2).
**Design document:** [sprint-2-persian-retrieval.md](sprint-2-persian-retrieval.md)

## 1. Objective

Extend the existing hybrid retrieval system (pgvector semantic + Postgres FTS + RRF) so Persian, English, and mixed Persian/English queries work at the lexical preprocessing layer and against a normalized search representation — while preserving the OpenAI API, the embedding model and dimensions, the retrieval architecture, RRF, filters, candidate/top-k, neighbor expansion, citation, and grounding behavior exactly as they are.

## 2. What Was Implemented

1. **Query-side normalization (Parts 2–3):** `DocumentRetriever.search` normalizes the query once via Sprint 1's `app.text.normalize()` and feeds the normalized text to both the query embedding and keyword extraction. The raw query is never persisted or rewritten.
2. **Persian-aware keyword extraction (Parts 4–8):** `keywords.py` gained a deterministic tokenizer (Persian letters incl. ZWNJ words, English words, numbers with `-`/`/`, Persian digits), a deterministic Persian/mixed extraction path (tokenize → per-token normalize → Persian-stopword + filler + company-token filtering → cap at 5), and Persian-safe deterministic fallbacks. Persian queries never take the English fast path or the LLM path; complex English queries keep the OpenAI structured-output refinement with its deterministic fallback.
3. **Stopword growth (Part 6):** `app/text/stopwords.py` grew from 36 to 48 entries with retrieval evidence: question words `چه چیست چگونه چرا کجا چند کدام چقدر چطور`, copula/auxiliary `هست بوده`, preposition `روی`.
4. **Search representation + migration (Parts 9–11):** new `document_chunks.search_text` TEXT column; `search_vector` regenerated as `to_tsvector('english', coalesce(search_text, text)) STORED` with its GIN index preserved; `pg_trgm` extension + GIN trigram index on `search_text` created (unused by queries — deferred per Part 21).
5. **Backfill (Parts 12, 26):** `backend/scripts/backfill_search_text.py` — idempotent, batched, dry-run capable, no OpenAI, no changes to `text`/embeddings/citations.
6. **Ingestion integration (Part 13):** `ingest/chunk_and_embed.py` writes `search_text = normalize(chunk.text)` for every new chunk (smallest possible integration; SEC ingestion design unchanged).
7. **Tests (Parts 18–20):** 42-query golden set + 5 new test modules (fast) + 1 integration-marked module.
8. **Documentation (Part 31):** `docs/sprint-2-persian-retrieval.md` and this report.

**Explicitly not done (per brief):** no reranker, no BGE-M3/embedding changes, no grounding/citation changes, no frontend changes, no PDF/DOCX/OCR work, no RRF or ranking changes.

## 3. Query Normalization Flow

```text
raw_query (unchanged everywhere user-facing)
    ↓ normalize()  — once, in DocumentRetriever.search
normalized_query
    ├─→ embed_query(normalized_query)               (semantic leg, model/dims unchanged)
    └─→ extract_fts_keywords(normalized_query)      (lexical preprocessing)
            ↓ deterministic extractor (Persian/mixed) or fast-path/LLM (English)
        keyword string → plainto_tsquery('english', …) over search_vector
```

Normalization is effectively lossless for English (whitespace-only), so a single path serves all languages. `queries.py` needed no change: it already queries `search_vector`, whose generated expression now consumes the normalized representation.

## 4. Keyword Extraction Changes

- `keywords.py` retains all English machinery (filler/low-value lists, SEC phrases, capitalized-token ranking, ticker suppression, OpenAI refinement + fallback) — pre-existing `test_keywords.py` passes unmodified.
- Added: `tokenize()` (deterministic lexical tokenizer), `_contains_arabic_script()` router, `_deterministic_persian_keywords()` (order-preserving, stopword-filtered, capped at `retrieval_fts_keyword_max`), Persian-aware `_deterministic_fallback`.
- Extracted tokens are normalized before output, so keyword spelling always matches `search_text` spelling.
- Routing: any Arabic-script character → deterministic Persian path (no fast path, no LLM); otherwise existing English behavior.
- The Persian path never emits an empty keyword string for content-bearing queries; an all-stopword query returns the original string (old fallback contract).

## 5. Search Representation

```text
document_chunks.text          — canonical original text (citations/excerpts/grounding) — UNCHANGED
document_chunks.search_text   — normalize(text); search-only; nullable
document_chunks.search_vector — GENERATED ALWAYS AS (to_tsvector('english', coalesce(search_text, text))) STORED
```

## 6. Database Migration

One new revision on top of head `d2e4b7a9c1f3` (no history rewritten):

- **File:** `backend/alembic/versions/b8e3d5a1f4c2_add_search_text_normalized_search_vector.py`
- **Revision:** `b8e3d5a1f4c2` (down_revision `d2e4b7a9c1f3`)
- **Upgrade:** `CREATE EXTENSION pg_trgm` → `ADD COLUMN search_text TEXT` → drop GIN index → drop + re-add `search_vector` (generated columns cannot be altered in place) → recreate GIN index → trigram GIN index on `search_text`.
- **Downgrade:** reverses every step (original generated expression + index restored; `search_text` and `pg_trgm` dropped).
- **FTS config decision:** `retrieval_fts_config` stays `'english'` — for Persian tokens `'english'` ≡ `'simple'` (the english snowball stemmer never matches non-ASCII words; no Persian entries in `english.stop`; same parser), while `'simple'` would regress English (fast-path queries rely on query-side english stopword removal; document-side English stemming would be lost). Column and query config remain internally consistent. Documented in `docs/sprint-2-persian-retrieval.md` §5.
- `queries.py`, `config.py`: **not modified** (not needed — see §5/§6 rationale; the brief's expected-change list marked config.py "only if needed").
- Note: adding a stored generated column rewrites `document_chunks` once (Postgres requirement) — one-time, acceptable at current scale.

## 7. Backfill Strategy

`uv run python -m scripts.backfill_search_text` (from `backend/`):

- `search_text = normalize(text)` via the canonical Python normalizer (no SQL duplicate).
- Idempotent (verified live: second run reports `0 updated, N already correct`).
- Keyset batching (`--batch-size`, default 500), per-batch commits, progress output, `--dry-run`.
- Never modifies `text`; no re-embedding; no OpenAI; no citation changes.
- The generated `search_vector` updates automatically as rows are written.
- New ingestion writes `search_text` directly, so backfill only concerns pre-existing chunks.

## 8. Existing English Behavior

- Fast path, LLM refinement, heuristics, budgets, prompts: unchanged (existing `test_keywords.py` green without modification).
- FTS config unchanged (`'english'`): stemming and query-side stopword removal identical.
- Empirical old-vs-new regression battery (throwaway PostgreSQL 16.14): for a pure-English chunk, an `old_sv = to_tsvector('english', text)` column and the new `search_vector` produced **identical hit sets for every English query tested** (11-query battery, e.g. "What are Microsoft's major risks?" → `[1]` on both; "major risk" → `[1]` on both — stemming intact).
- All pre-existing retrieval tests pass without weakened assertions (Part 30).

## 9. Mixed Persian/English Behavior

Deterministic extraction preserves both scripts and numbers (golden set, subset shown):

| Query | Keywords |
| --- | --- |
| `ریسک‌های Microsoft در سال 2024 چیست؟` | `ریسک‌های Microsoft سال 2024` |
| `AWS چه تأثیری روی revenue شرکت داشته؟` | `AWS تأثیری revenue شرکت داشته` |
| `در 10-K 2024 وضعیت cloud revenue چگونه بوده؟` | `10-K 2024 وضعیت cloud revenue` |
| `مهم‌ترین risks شرکت چیست؟` | `مهم‌ترین risks شرکت` |

Semantic retrieval still runs on the normalized query; lexical retrieval receives these keywords; RRF still receives both rankings (orchestration tests assert both legs called once with unchanged `candidate_k`/`filters`).

## 10. Tests Added

| File | Content |
| --- | --- |
| `tests/retrieval/golden_queries.py` | 42-case golden set: 22 Persian, 10 English, 10 mixed; contracts (`must_include`/`must_exclude`) + fixture documents with unnormalized spellings for normalization-equivalence proofing |
| `tests/retrieval/test_golden_queries.py` | Harness: per-query contract + keyword⊆normalized-document-representation assertion (Part 18/20) |
| `tests/retrieval/test_keywords_persian.py` | 10 unit tests: Persian token survival, stopword/question-word removal, mixed token survival, budget, Arabic-variant equivalence, fallback Persian-safety, tokenizer punctuation/ZWNJ/hyphen behavior |
| `tests/retrieval/test_retriever_persian.py` | Orchestration: normalized query reaches both legs; Persian keywords reach the lexical leg; `candidate_k`/filters/RRF/hydration unchanged |
| `tests/retrieval/test_fts_representation.py` | Normalization equivalence classes + the Part 20 example (variant spellings/digit families must match) |
| `tests/retrieval/test_retrieval_persian_integration.py` | `@pytest.mark.integration`: all Persian/mixed golden queries through the live hybrid pipeline (deselected until credentials + corpus exist) |

## 11. Test Results

All commands run from `backend/` with the five required env vars present as placeholders (Sprint 0 finding K2; no `.env` created). No results invented.

```text
Focused retrieval tests   uv run pytest tests/retrieval -m "not integration"
                          → 113 passed, 14 skipped, 34 deselected

Full non-integration      uv run pytest -m "not integration"
                          → 233 passed, 14 skipped, 36 deselected
                          (Sprint 1 baseline: 139 passed, 4 deselected; +94 new passing,
                           +14 parametrized skips [golden entries without fixture docs /
                           English entries], +32 new integration deselected)

Ruff                      uv run ruff check . → All checks passed!

Migration validation      PASS — offline: alembic history/heads (single head b8e3d5a1f4c2),
                          upgrade/downgrade SQL generation; live: real alembic upgrade →
                          downgrade → re-upgrade round-trip on a faithful pre-migration
                          document_chunks replica (throwaway PostgreSQL 16.14, trust auth,
                          isolated temp instance, deleted afterwards)
Backfill (live)           PASS — run 1: "updated 3 row(s)"; run 2: "updated 0 row(s),
                          3 already correct" (idempotent)
FTS behavior (live)       Persian-normalized queries match the new search_vector where the
                          old column returned nothing (e.g. "شرکت سال 1403": old [], new [0]);
                          English battery identical old-vs-new (zero regression); PG 16.14
                          empirically keeps ZWNJ words whole ('ریسک‌های':1) on both the
                          document and query side
```

Live end-to-end retrieval against the real SEC corpus was **not** executed (no credentials/corpus in this environment) — the integration test file exists for that purpose and is deselected by design.

## 12. Files Created

```text
backend/alembic/versions/b8e3d5a1f4c2_add_search_text_normalized_search_vector.py
backend/scripts/backfill_search_text.py
backend/tests/retrieval/golden_queries.py
backend/tests/retrieval/test_golden_queries.py
backend/tests/retrieval/test_keywords_persian.py
backend/tests/retrieval/test_retriever_persian.py
backend/tests/retrieval/test_fts_representation.py
backend/tests/retrieval/test_retrieval_persian_integration.py
docs/sprint-2-persian-retrieval.md
docs/sprint-2-report.md                                   (this file)
```

## 13. Files Modified

```text
backend/app/retrieval/retriever.py        normalize query once; feed both legs
backend/app/retrieval/keywords.py         Persian-aware tokenizer + deterministic Persian path
                                          + Persian-safe fallbacks + routing; English machinery kept
backend/app/text/stopwords.py             36 → 48 entries (question words, هست/بوده, روی) + docstring
backend/app/database/models/document_chunk.py   search_text column + docstring
backend/ingest/chunk_and_embed.py         writes search_text=normalize(record.text) at insert
```

Not modified (and why): `queries.py` (FTS SQL already targets `search_vector`, whose definition changed in the migration), `config.py` (`retrieval_fts_config` deliberately stays `'english'`), `fusion.py`/`embeddings.py` (unchanged by design), grounding/citation/streaming/frontend/SEC-ingestion (out of scope, untouched).

## 14. Regression Check

Explicitly confirmed:

- **OpenAI embedding unchanged** — `embed_query`/`embed_texts` untouched; `text-embedding-3-small`, 1536 dims.
- **OpenAI chat unchanged** — agent, grounding judge, keyword-refinement model untouched.
- **Supabase unchanged** — auth, REST persistence, RLS untouched.
- **PydanticAI unchanged** — agent/tools/deps/outputs untouched.
- **RRF unchanged** — `reciprocal_rank_fusion` untouched; both rankings still feed it.
- **Grounding unchanged** — `grounding/validator.py`, `assistant/deps.py`, `assistant/outputs.py`, `chat/orchestrator.py` untouched.
- **Citation unchanged** — no excerpt/registry/persistence behavior touched.
- **Frontend unchanged** — zero frontend files modified.
- **SEC ingestion preserved** — pipeline shape unchanged; only an additive `search_text` write at insert.
- **`document_chunks.text` preserved** — written nowhere; `normalize()` has no write path to it; backfill only reads it.
- English retrieval behavior verified unchanged empirically (§8) and by the untouched pre-existing test suite.

## 15. Known Limitations

- No Persian morphology: `ریسک` ≠ `ریسک‌های` and `رشد` ≠ `رشدی` post-normalization (PG 16 keeps ZWNJ words whole); differing word forms rely on the semantic leg.
- AND semantics retained: all extracted keywords must co-occur; long Persian queries can still miss lexically.
- Space vs ZWNJ variants of the same word do not cross-match (Sprint 1 ZWNJ policy, applied consistently).
- Stopword set remains deliberately small (48 entries).
- No LLM refinement for Persian (deliberate); deterministic Persian term quality unvalidated against real Persian documents.
- Trigram index created but unused by queries.
- Live end-to-end against the real SEC corpus not run (no credentials/corpus).

## 16. Deferred Work

- **Reranker** (BGE / cross-encoder / any reranking provider) — later quality sprint; explicitly not implemented.
- **BGE-M3** — not implemented.
- **Embedding replacement / dimension migration / new embedding provider** — not implemented.
- **Suffix folding** (`ها/های/تر/ترین`) — deferred; must live in `normalize.py` with evaluation.
- **Advanced Persian morphology** — deferred.
- **PDF/DOCX/OCR ingestion** — not implemented (no code path exists).
- **Persian UI/RTL/i18n** — not implemented; frontend untouched.

## 17. Recommendation for Sprint 3

1. **Run the live validation the moment credentials + corpus exist:** `uv run alembic upgrade head`, `uv run python -m scripts.backfill_search_text`, then `uv run pytest -m integration` (includes the new Persian golden-query pipeline smoke) plus `scripts/smoke_retrieval.py` with a couple of Persian queries added. This sprint's Persian retrieval is verified at the unit level and against a live scratch Postgres, but not yet against the real corpus.
2. **Measure before morphological work:** log lexical-leg hit rates for the golden Persian queries against the real corpus; only if recall is the bottleneck (not ranking) implement suffix folding inside `normalize.py` (it affects both query and corpus sides, and requires a re-backfill).
3. **Then** the reranker sprint (Part 22 deferral) is the next quality lever, after lexical recall is measured.
