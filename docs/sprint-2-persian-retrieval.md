# Sprint 2 — Persian-Aware Retrieval

**Deliverable:** additive Persian/English/mixed lexical-retrieval support on top of the existing hybrid pipeline.
**Companion report:** [sprint-2-report.md](sprint-2-report.md) (exact files, commands, results).
**Sprint 1 prerequisite:** [persian-text-normalization.md](persian-text-normalization.md) (`app.text.normalize`, `app.text.stopwords`).

> The existing OpenAI embedding model remains unchanged in Sprint 2.
>
> `document_chunks.text` remains the canonical citation source.

---

## 1. Existing retrieval architecture (unchanged shape)

```text
User Query
    │
    ├── normalize()                      ← Sprint 2 addition (retrieval preprocessing only)
    │
    ├── Semantic Search (pgvector, OpenAI text-embedding-3-small, 1536 dims)
    │
    └── Lexical / FTS Search (plainto_tsquery + ts_rank_cd over search_vector)
             │
             ▼
        RRF Fusion (k=60, unchanged)
             │
             ▼
      Hydration + Neighbors (unchanged)
```

`DocumentRetriever.search` (`backend/app/retrieval/retriever.py`) still orchestrates: embed ∥ keywords in parallel → dual SQL search with separate sessions → `reciprocal_rank_fusion` → hydrate + neighbor expansion. `candidate_k=50`, `top_k=10`, `retrieval_rrf_k=60`, `retrieval_neighbor_radius=1`, filters, and the `TurnRegistry`/grounding/citation behavior are untouched.

## 2. Why Persian retrieval needed changes

Three lexical-layer defects (documented in the baseline, §8/K7) made Persian lexical search non-functional:

1. **No normalization anywhere near retrieval** — the same Persian word spelled with Arabic `ي/ك` vs Persian `ی/ک`, Persian vs Arabic-Indic digits, or with diacritics compared unequal, so lexical matches failed on spelling variance.
2. **`keywords.py` was ASCII-only** — its token regexes (`[A-Za-z0-9]…`) could not see Persian characters at all; Persian tokens vanished from the keyword string.
3. **No Persian stopword handling** — `plainto_tsquery` ANDs every word, so one ANDed question word (`چیست`) or particle (`با`) zeroes out the lexical leg; the `'english'` config's stopword list contains no Persian words.

Sprint 2 closes all three additively without touching the retrieval architecture, fusion semantics, embeddings, or schema beyond one derived column.

## 3. Query normalization flow

Normalizing happens **once**, in the orchestrator (`retriever.py`), and both retrieval legs consume the result:

```text
raw_query (unchanged in chat history / persistence)
    ↓  app.text.normalize()   — Sprint 1 canonical normalizer
normalized_query
    ├──────────────→ embed_query(normalized_query)      (semantic leg)
    └──────────────→ extract_fts_keywords(normalized_query)  (lexical preprocessing)
```

Responsibilities stay separated (Part 15): `normalize.py` owns normalization, `keywords.py` owns lexical term selection, `queries.py` owns SQL, `retriever.py` owns orchestration. The raw user query is never rewritten: normalization is retrieval preprocessing only, and message persistence/citations are untouched.

Embedding the normalized query is safe for English: for ASCII text `normalize()` only collapses whitespace — effectively lossless — so one consistent path serves all languages.

## 4. Search_text design

`document_chunks` gains a **derived, search-only** representation:

```text
search_text = normalize(text)     — written by ingestion and backfill
search_vector tsvector GENERATED ALWAYS AS (
    to_tsvector('english', coalesce(search_text, text))
) STORED                          — rebuilt generated column
```

- `text` is never read for rewriting and remains the citation/excerpt/grounding canon.
- `coalesce(search_text, text)` keeps the column meaningful before the backfill runs (falls back to the pre-Sprint-2 behavior).
- `search_vector` remains a stored generated column, so the FTS SQL in `queries.py` needed **no changes at all** — it still queries `search_vector`; only the generated expression's input changed.

## 5. FTS configuration decision (kept `'english'` — not `'simple'`)

The brief's *preferred target* was `to_tsvector('simple', …)`. After verification this sprint **keeps `'english'` on both the generated column and the query side** (`retrieval_fts_config` unchanged in `config.py`). Reasons:

1. **For Persian tokens, `'english'` and `'simple'` behave identically.** The english snowball stemmer's suffix rules are ASCII-based and never match non-ASCII (Persian) words — verified empirically on PostgreSQL 16.14: Persian words index verbatim. `english.stop` contains no Persian words. Both configs use the same default parser.
2. **Switching to `'simple'` would regress English.** Concretely: the English fast path returns short queries verbatim (`"How did revenue change?"`) and relies on the `'english'` config removing `how`/`did` at query time — under `'simple'` those become AND terms with near-zero lexical recall. Document-side English stemming (`risks`→`risk`) would also be lost.
3. **Zero configuration drift.** Column and query config stay internally consistent (`'english'` both sides) with no `config.py` change.

Empirical backing (throwaway PostgreSQL 16.14, see report §11): all-English query battery produced **identical hit sets against the old column (`to_tsvector('english', text)`) and the new column** — a direct regression check; a normalized Persian query that misses the old column hits the new one.

Also verified empirically on PostgreSQL 16.14: the default parser treats ZWNJ between Arabic letters as a **word character** (`ریسک‌های` indexes as one lexeme), and it does so identically on the document side and the `plainto_tsquery` query side — so ZWNJ handling is consistent regardless of the dictionary config.

## 6. Keyword extraction strategy

`backend/app/retrieval/keywords.py` keeps its full English machinery (filler/low-value lists, SEC phrases, capitalized-token ranking, ticker-prefix suppression, OpenAI structured-output refinement for long English queries, deterministic fallback on LLM failure) and adds a deterministic Persian-aware layer:

```text
Persian/mixed query → tokenize → per-token normalize → drop Persian stopwords
                      → drop English fillers → drop company tokens → cap at 5
```

- **Tokenizer** (`tokenize`): English/number tokens keep internal `-` and `/` (`10-K`, `FY2024/25`); Persian/Arabic-script letters tokenize as words with internal ZWNJ preserved (`ریسک‌های`); Persian/Arabic-Indic digit codepoints are included so unnormalized input cannot lose numbers; Persian punctuation (`، ؛ ؟`) separates tokens.
- **Stopwords** come from Sprint 1's `app.text.stopwords` (single source of truth; no second list). The set grew from 36 to 48 entries with retrieval evidence: question words (`چه چیست چگونه چرا کجا چند کدام چقدر چطور`), the colloquial copula `هست`, the auxiliary `بوده`, and the preposition `روی` — filings never contain these, and a single ANDed one would zero the leg.
- **Extracted tokens are normalized** before output, so keyword spelling always matches the normalized `search_text` spelling even if a caller skips pre-normalization.
- **Persian queries never take the English fast path or the LLM path** — even short ones — because question-word removal is mandatory under AND semantics. This is the Part 8 decision: deterministic Persian-aware extraction is sufficient for Persian (documents and queries share vocabulary; normalization plus stopword removal does the work), while the SEC-tuned English prompt plus old heuristics could drop Persian tokens. LLM refinement remains available for complex English queries; LLM failure still falls back deterministically (and the fallback itself is now Persian-safe).
- Keyword budget stays `retrieval_fts_keyword_max = 5` (AND semantics); when no token survives filtering, the original query string is returned (mirrors the old fallback contract).

## 7. English compatibility strategy

- Fast path (≤ `retrieval_fts_keyword_fast_path_tokens` = 5 tokens) unchanged.
- LLM refinement path, prompt, merge heuristics, and budget logic unchanged.
- The only behavioral edit to the English fallback is swapping its ASCII-only token regex for the Persian-aware `tokenize` (a strict superset — identical output for ASCII input) and adding the Persian-stopword check. Verified: the full pre-existing `test_keywords.py` suite passes unmodified.
- FTS config unchanged (`'english'`), so stemming/stopword behavior is byte-identical — confirmed empirically old-column vs new-column (report §11).
- The whole pre-existing retrieval test suite passes without weakening any assertion (only the FTS-SQL test needed no change at all; none were weakened or removed).

## 8. Mixed Persian/English behavior

Mixed queries route to the deterministic Persian-aware extractor, which preserves both scripts:

| Query | Extracted keywords |
| --- | --- |
| `ریسک‌های Microsoft در سال 2024 چیست؟` | `ریسک‌های Microsoft سال 2024` |
| `AWS چه تأثیری روی revenue شرکت داشته؟` | `AWS تأثیری revenue شرکت داشته` |
| `در 10-K 2024 وضعیت cloud revenue چگونه بوده؟` | `10-K 2024 وضعیت cloud revenue` |
| `مهم‌ترین risks شرکت چیست؟` | `مهم‌ترین risks شرکت` |

Persian terms, English terms, and numbers all survive; stopword/question-word filtering applies; the result never collapses to empty for content-bearing queries (42-case golden set proves this per-query — `backend/tests/retrieval/golden_queries.py`).

## 9. Backfill strategy

`backend/scripts/backfill_search_text.py` populates `search_text = normalize(text)` for pre-existing chunks:

- Uses the canonical Python normalizer (`app.text.normalize`) — no SQL-side normalization duplicate.
- Idempotent: rows already equal to `normalize(text)` are skipped; repeat runs are no-ops (verified on a live scratch DB).
- Keyset-batched (`--batch-size`, default 500), commits per batch, reports progress.
- Never touches `text`, embeddings, or citations; needs no OpenAI access.
- `--dry-run` scans and reports without writing.
- Run from `backend/`: `uv run python -m scripts.backfill_search_text`.

New ingestion writes `search_text` at insert time (`ingest/chunk_and_embed.py`), so future chunks are born correct and no re-ingestion is needed for the lexical upgrade.

## 10. Schema / migration details

One migration on top of head `d2e4b7a9c1f3`:

**`backend/alembic/versions/b8e3d5a1f4c2_add_search_text_normalized_search_vector.py`**

1. `CREATE EXTENSION IF NOT EXISTS pg_trgm`
2. `ADD COLUMN search_text TEXT`
3. Drop + re-add `search_vector` as `GENERATED ALWAYS AS (to_tsvector('english', coalesce(search_text, text))) STORED` — generated columns cannot be altered in place; the GIN index on it is dropped explicitly first and recreated after (recreated identically: `ix_document_chunks_search_vector_gin`)
4. `CREATE INDEX ix_document_chunks_search_text_trgm USING gin (search_text gin_trgm_ops)`

No historical migration was edited. The downgrade reverses every step (restores the original generated column expression and index, drops `search_text` and `pg_trgm`). Adding a stored generated column rewrites the table once (Postgres requirement) — a one-time cost documented in the report.

**pg_trgm role (Part 21):** the extension and trigram GIN index are created now to support a future fuzzy/OCR sprint, but **no query uses trigram matching** — integrating `similarity()` into the tsquery leg would change ranking semantics, so query integration is deliberately deferred; the index's current role is "in place, unused, documented".

## 11. Test strategy

Corpus-free by design (the repository snapshot ships no SEC corpus; live credentials are unavailable):

- **Golden set** (`tests/retrieval/golden_queries.py`): 22 Persian + 10 English + 10 mixed queries with per-query contracts (`must_include`, `must_exclude`, optional fixture `doc_text`). No invented expected *answers* — fixture documents exist only to pin the normalization equivalence: every extracted keyword must appear in `tokenize(normalize(doc_text))`, i.e. the AND-semantics lexical leg can match the fixture.
- **Keyword extraction units** (`test_keywords_persian.py`): Persian tokens survive, stopwords/question words removed, English tokens and numbers survive in mixed queries, budget respected, Arabic-variant spellings produce identical normalized keywords, deterministic fallback keeps Persian tokens, tokenizer punctuation/ZWNJ/hyphen behavior.
- **Orchestration units** (`test_retriever_persian.py`): both legs receive the normalized query; semantic leg called with unchanged `limit`/`filters`; lexical leg receives Persian keywords; fusion/hydration unchanged.
- **Search representation** (`test_fts_representation.py`): normalization equivalence classes (yeh/kaf, digit families, presentation forms, diacritics, tatweel, ZWNJ policy) and the Part 20 requirement — a variant-spelled query matches the normalized document representation.
- **Integration** (`test_retrieval_persian_integration.py`, `@pytest.mark.integration`, deselected in the fast suite): runs all Persian/mixed golden queries through the live hybrid pipeline once credentials + corpus exist.
- **Live migration validation** was additionally performed against a throwaway PostgreSQL 16.14 instance (see report §11): real `alembic upgrade/downgrade/upgrade` round-trip on a faithful pre-migration replica, real backfill runs, old-vs-new column regression battery, and end-to-end `plainto_tsquery` matching for Persian/English queries.

## 12. Known limitations

- **No Persian morphology** (Sprint 1 policy): `ریسک` does not match `ریسک‌های` (PG 16 keeps ZWNJ words whole), and `رشد` ≠ `رشدی`. Golden fixture documents are crafted so extracted keywords appear verbatim; real-corpus recall relies on the semantic leg when forms differ. Suffix folding stays deferred (Sprint 1 §13 recommendation) until it can live inside `normalize.py` and be evaluated.
- **AND semantics** remain: all extracted keywords must appear in a chunk. Long Persian queries with 5 content words can still miss lexically; the semantic leg carries recall. (Raising the budget does not help; the alternative — OR semantics — changes ranking and is out of scope.)
- **Space vs ZWNJ variants** of the same word do not cross-match (`می روم` vs `می‌روm`) — inherent to the Sprint 1 ZWNJ policy, applied identically to queries and documents.
- **Stopword set is still small** (48 explicit entries) and conservative by design.
- **No LLM refinement for Persian** (deliberate; see §6) — the deterministic extractor's term quality is untested against real Persian documents.
- **Trigram index is unused** by queries in this sprint.
- **Live end-to-end against the real SEC corpus has not been run** (no credentials/corpus in this environment); the integration test file exists for when they are available.

## 13. Deferred work

- **Reranker** (BGE / cross-encoder / any reranking provider) — later quality sprint; explicitly not implemented.
- **BGE-M3 / any embedding change** — the OpenAI `text-embedding-3-small` (1536 dims) path is untouched.
- **Suffix folding** (`ها/های/تر/ترین`) and advanced Persian morphology — must go through `normalize.py` with evaluation.
- **PDF/DOCX/OCR ingestion paths** — no code exists; out of scope.
- **Persian UI/RTL/i18n** — frontend untouched.
- **Trigram query integration** for fuzzy/OCR retrieval — index created, query use deferred.
