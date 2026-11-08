# Sprint 1 Report — Persian Language Core

**Date:** 2026-09-10
**Branch context:** `development` (workspace is a content-verified snapshot; no git metadata — see `docs/baseline.md` §2).

## 1. Objective

Implement the Persian Language Core as a small, deterministic, reusable backend subsystem: one canonical Persian text-normalization layer plus a conservative Persian stopword set, with no integration into retrieval, ingestion, database, embeddings, or UI.

## 2. What Was Implemented

- `backend/app/text/normalize.py` — `normalize(text: str) -> str`, a pure-stdlib, deterministic, idempotent normalizer composed of seven ordered stages, exposed via five narrowly scoped helpers (`normalize_codepoints`, `normalize_digits`, `strip_diacritics`, `normalize_zwnj`, `normalize_whitespace`).
- `backend/app/text/stopwords.py` — `PERSIAN_STOPWORDS: frozenset[str]` (36 explicit entries) and `is_stopword(token) -> bool` (normalizes its input before lookup).
- `backend/app/text/__init__.py` — public surface: `normalize`, `PERSIAN_STOPWORDS`, `is_stopword` (mirrors `app/retrieval/__init__.py` style).
- `docs/persian-text-normalization.md` — full policy documentation.
- Comprehensive behavior tests (49) and a small stopword test module (3).

Verified before implementation: no existing normalization logic to reuse — `_normalize_terms` in `backend/app/retrieval/keywords.py:119` is only strip/casefold/dedup, as the baseline stated. The new package is therefore the single source of truth for Persian normalization; no logic was duplicated.

## 3. Normalization Rules

Applied (in pipeline order — full detail in `docs/persian-text-normalization.md`):

1. Arabic presentation forms (U+FB50–FDFF, U+FE70–FEFF) → standard letters via **block-scoped NFKC**.
2. Arabic letter variants fold to Persian: `ي`→`ی`, `ى`→`ی`, `ك`→`ک`.
3. Persian `۰-۹` and Arabic-Indic `٠-٩` digits → ASCII.
4. Combining-mark removal: tashkeel (U+064B–065F: fatha, damma, kasra, shadda, sukun, tanwin), annotation signs (U+0610–061A), superscript alef (U+0670), Quranic marks (U+06D6–06DC, 06DF–06E8, 06EA–06ED), plus tatweel (U+0640).
5. Bidi formatting controls removed (LRM/RLM, embeddings, isolates).
6. ZWNJ cleanup (see §4).
7. Whitespace: tabs/NBSP/narrow spaces → single space; newline runs capped at one blank line; edges stripped; paragraph boundaries preserved.

Intentionally NOT applied (each documented with its reason in the doc): stemming/suffix folding, morphological reconstruction, hamza folding (`أ إ ؤ ئ`), `ة`/`ۀ` folding, `آ`→`ا`, punctuation rewriting, ZWJ removal, transliteration, broad whole-string NFKC, tokenization.

## 4. ZWNJ Policy

- **Kept** only between two Arabic-script letters, where it prevents cursive joining and is meaningful (`می‌روم`, `هم‌کاران`).
- **Dropped** when adjacent to whitespace, punctuation, digits, Latin text, or string boundaries (`می‌ رود` → `می رود`).
- **Repeated runs collapse** to one ZWNJ. **Never rewritten to a space; never deleted wholesale.**
- A single stray ZWNJ inside a word (`می‌ر‌وم`) is preserved — indistinguishable from a legitimate boundary without morphology, which is explicitly out of scope.

## 5. Stopword Strategy

Small, explicit, conservative frozenset of 36 standalone function words: the 18 words named in the sprint brief plus minimal copulas/auxiliaries, pronouns, and connectives. No internet list copied; no LLM calls; no NLP dependency. Entries stored in normalized spelling; `is_stopword` normalizes its input so raw tokens work. Growth is deferred to Sprint 2 retrieval evaluation evidence.

## 6. Files Created

```text
backend/app/text/__init__.py
backend/app/text/normalize.py
backend/app/text/stopwords.py
backend/tests/text/__init__.py
backend/tests/text/test_normalize.py
backend/tests/text/test_stopwords.py      (justified addition — see §7)
docs/persian-text-normalization.md
docs/sprint-1-report.md                   (this file)
```

## 7. Files Modified

**None.** No existing file was touched. One file beyond the brief's expected list was created: `backend/tests/text/test_stopwords.py` — the stopword module is a Sprint 1 deliverable with real behavior (`is_stopword` normalization contract, set contents), and the brief explicitly allows "additional small test/data files if clearly justified." Testing it inside `test_normalize.py` would have misnamed the coverage.

## 8. Tests Added

- `backend/tests/text/test_normalize.py` — 46 tests in 8 behavior groups: Arabic letter variants (incl. U+FEFB presentation form, tatweel), digit families, diacritics (attached/standalone/punctuation-survival), ZWNJ policy (all five cases from the brief), whitespace (paragraph preservation, CRLF), mixed Persian/English, trivial inputs (`""`, `" "`, `"\n"`, `None` → `TypeError`), preservation, and idempotence parametrized over 17 fixtures.
- `backend/tests/text/test_stopwords.py` — 3 tests: core function words present, content words absent, `is_stopword` normalizes input.

Tests assert input → expected output only; no internal-helper assertion tests.

## 9. Test Results

All commands executed from `backend/` (repository convention) with the five required env vars present as placeholders (known Sprint 0 finding K2 — `Settings()` fails fast at import; no `.env` was created):

```text
focused tests:            49 passed   (uv run pytest tests/text/ -q)
full non-integration:     139 passed, 4 deselected (integration, by design)
                          (uv run pytest -m "not integration" — 90 pre-existing + 49 new)
ruff:                     PASS        (uv run ruff check . — All checks passed)
```

No results invented; first run had 2 failures caused by a misspelled fixture (kaf placed one letter early in `شركت`) — fixture corrected, implementation unchanged.

## 10. Regression Check

Confirmed — nothing pre-existing changed:

- OpenAI, Supabase, PydanticAI, embeddings, retrieval pipeline, FTS schema/queries, RRF, agent tools, grounding validator, `TurnRegistry`, citation behavior, streaming: **untouched** (zero modifications to existing source files).
- `document_chunks.text` contract: no code path calls `normalize()` yet; canonical text untouched.
- Database: **no migration created, no schema change, no DB contact.**
- Frontend: **no files modified.**
- English functionality: no behavior change possible — the new package is imported by nothing except its own tests.
- No dependency added (pure stdlib: `re`, `unicodedata`).

## 11. Deferred Work

Intentionally NOT done in Sprint 1: Persian FTS; retrieval integration (`queries.py`, `retriever.py`, `candidate_k`, `top_k`, RRF); keyword-extraction integration (`keywords.py` stays ASCII-only); ingestion integration (`chunking.py`, `chunk_and_embed.py`, `embeddings.py` untouched); PDF/DOCX/OCR integration; embedding changes; LLM prompt changes; UI/RTL/i18n; database schema changes; stemming/suffix folding; Persian tokenizer; search-representation storage.

## 12. Known Limitations

- The stray-ZWNJ case (`می‌ر‌وم`) is preserved, not repaired (needs morphology).
- The stopword set is minimal by design and unvalidated against real queries.
- `normalize_codepoints` loops per character in Python — fine for current volumes; profile before bulk-ingesting large Persian corpora.
- Block-scoped NFKC decomposes isolated presentation forms to letters, losing joining context inherent in those forms; mid-word isolated forms were already malformed.
- Live smoke/integration tests remain unrun (no credentials/corpus in this environment — unchanged from Sprint 0).

## 13. Recommendation for Sprint 2

Integrate the layer into retrieval additively:

1. **Query side first (zero schema change):** in `DocumentRetriever.search`, normalize the query before `extract_fts_keywords` and before embedding; make `keywords.py` Persian-aware (tokenize on non-letter/non-digit boundaries, drop `PERSIAN_STOPWORDS`, keep ≤5-word budget for `plainto_tsquery` AND-semantics).
2. **Corpus side:** add a derived normalized column (e.g. `search_text`) via one Alembic migration + a generated/stored strategy, populate it from `normalize(chunk.text)` during ingestion, and point the FTS leg at it (likely `'simple'` config, since no Persian dictionary exists in Postgres).
3. **Evaluate before expanding:** build a small Persian query/golden-set harness and measure recall/precision before adding suffix folding (`ها/های/تر/ترین`) to the normalizer — folding affects both query and corpus sides and must stay inside this single module.
4. Keep `document_chunks.text` as the citation canon throughout.
