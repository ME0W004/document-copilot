# Sprint 3 Report — Persian LLM + Grounding

**Date:** 2026-09-11
**Branch context:** `development` (workspace is a content-verified snapshot; no git metadata — see `docs/baseline.md` §2).
**Design document:** [sprint-3-persian-llm-grounding.md](sprint-3-persian-llm-grounding.md)

## 1. Objective

Make the existing Document Copilot language-aware at the LLM/agent and grounding level: Persian questions get Persian answers, English questions get English answers, mixed questions get natural primarily-Persian answers, and Persian source passages remain fully citable — with every grounding, citation, and fail-closed guarantee intact and OpenAI/PydanticAI/embeddings/retrieval/Supabase/frontend untouched.

## 2. What Was Implemented

1. **Language-aware agent instructions** (`assistant/instructions.md`): new additive `## Answer language` section implementing the brief's policy (same language as the question; source language independent; technical terms preserved; ASCII citation markers in every language; natural Persian prose/punctuation with Markdown preserved), plus two minimal wording insertions (search queries may be in any language; excerpts must stay in the chunk's original language and never be translated).
2. **Language-neutral structured-output description** (`assistant/outputs.py`): `GroundedAnswer.answer` description changed from "Plain-English answer with [n] citation markers" to "Answer in the user's language with ASCII [n] citation markers". This description ships inside the JSON schema PydanticAI sends on every request, so it conditioned every answer toward English. Schema shape unchanged.
3. **ASCII citation-marker enforcement** (`grounding/validator.py`): `_CITATION_MARKER_RE` compiled with `re.ASCII`. Python's Unicode `\d` (and `int()`) accepted Persian `[۱]` / Arabic-Indic `[١]` markers, violating the documented ASCII contract that the frontend (JavaScript `\d`) actually implements; such answers would pass validation and render as un-clickable text. The fix makes validation stricter (fail-closed), never weaker.
4. **Language-neutral grounding judge** (`grounding/validator.py`): one added rule — judge support regardless of language; never reject a citation merely because answer and source differ in language; do not translate source_text. Support criterion, injection rule, and fail-closed behavior untouched.
5. **Tests**: 27 fast unit tests + 4 integration-marked live tests (see §7).
6. **Documentation**: the design document and this report.

Audited and deliberately **unchanged**: `assistant/tools.py` (descriptions already language-neutral; no tool-semantics change), `assistant/status.py` + `chat/orchestrator.py` status strings and `chat/streaming.py` `GROUNDING_FAILURE_MESSAGE` (English display text kept stable until the frontend localization sprint; stage identifiers and SSE contract unchanged — Parts 15–16), `retrieval/*` (Sprint 2 scope), embeddings, database, frontend.

## 3. Language Policy

- **Persian question → Persian answer** (natural Persian prose, Persian punctuation, Markdown structure preserved; company names, tickers, filing identifiers, and technical financial terms stay English where translation/transliteration would hurt; no transliteration of technical identifiers).
- **English question → English answer** (unchanged behavior; nothing about the Persian additions alters it).
- **Mixed question → primarily the dominant question language** (per the matrix: primarily Persian), with technical terms kept naturally (e.g. `نرخ رشد revenue شرکت` may stay natural).
- **Answer language ⊥ source language**: a Persian answer may cite English passages and vice versa; excerpts and citation metadata always remain in the source's original language.
- **Citation markers are ASCII `[n]` in every language**; normal numeric content may use whatever representation the model naturally generates.

## 4. Agent Instruction Changes

`backend/app/assistant/instructions.md` — three additive edits, everything else byte-identical (no rewrite of product logic; research/citation/refusal/stock-pick/evidence rules all preserved verbatim):

1. New `## Answer language` section (6 bullets) between *Product contract* and *Corpus scope*.
2. *Tool usage* step 1: added sentence "Search queries may be in any language."
3. *Output format* final paragraph: excerpts must be copied "in the chunk's original language"; `translate` added to the forbidden rewrites.

## 5. Grounding Changes

Two, both proven by inspection, both fail-closed-strict:

| Change | Why | Direction |
| --- | --- | --- |
| `_CITATION_MARKER_RE = re.compile(r"\[(\d+)\]", re.ASCII)` | Python `\d` matches Unicode `Nd` digits — verified `[۱]`/`[١]` matched and `int("۱") == 1` — so the validator accepted markers the ASCII contract and the frontend's JS `\d` parser reject | **Stricter** (enforces existing contract) |
| Judge prompt: language-neutrality rule added | Judge could treat answer/source language mismatch as non-support | Prevents false negatives only; criterion unchanged |

Everything else in `GroundingValidator` audited and left unchanged: excerpt/source reach the judge verbatim with **no normalization** (proven by a strict-verbatim test), Pydantic v2 parsing and JSON handling are Unicode-safe, indices logic is integer-based.

## 6. Citation Behavior

Unchanged and pinned by tests: `TurnRegistry` sole allowlist; excerpts verbatim from canonical `document_chunks.text` (`search_text` is never consulted for citations — it is only the FTS input via `search_vector`); `[n]` ↔ `citation_index` exact match, unique, 1-based, contiguous, ASCII; `insufficient_evidence` ⇒ zero citations; one retry then controlled `GROUNDING_FAILURE_MESSAGE`; citation persistence and `ON DELETE RESTRICT` untouched.

## 7. Tests Added

| File | Count | Content |
| --- | --- | --- |
| `tests/grounding/test_persian_grounding.py` | 17 | Brief's Cases A–J: Persian/Persian, Persian/English, English/Persian, mixed/bilingual supported; invalid citation, unregistered chunk, fabricated excerpt, insufficient-evidence-with-citations all fail; insufficient-evidence-Persian zero-citations passes; ASCII `[1]` passes; `[۱]` and `[١]` fail the ASCII contract; Persian-digit markers not pruned as referenced; special-character excerpt (ي ی ك ک ZWNJ ۱۲۳ ١٢٣ ، ؛ ؟ + English terms) reaches the judge verbatim; strict-verbatim judge proves no normalization inside citation validation; Persian prune behavior |
| `tests/assistant/test_persian.py` | 9 | Instructions language-policy contract (question→answer mapping, source/answer independence, technical terms, ASCII markers, `[۱]` named forbidden); existing safety rules still present; `answer` description language-neutral ("Plain-English" absent from schema); `GroundedAnswer`/`Citation` schema shape pinned unchanged; Persian tool-result formatting (verbatim + ZWNJ survival; 800-char truncation) |
| `tests/chat/test_streaming_persian.py` | 1 | Persian answer (ZWNJ + `[1]` + citation with Persian excerpt) streams through the AI SDK SSE format and JSON-round-trips to the exact original text |
| `tests/assistant/test_agent_persian_integration.py` | 4 | `@pytest.mark.integration` (deselected until credentials + corpus): Persian query → Persian grounded answer; English query → English answer; mixed query → primarily Persian; Persian underspecified stock-pick question → zero citations. Assertions use script presence (`[\u0600-\u06FF]`) and structural contracts, never exact prose |

## 8. Test Results

All commands run from `backend/` with the five required env vars present as placeholders (Sprint 0 finding K2; no `.env` created). No results invented.

```text
Focused new tests      uv run pytest tests/grounding/test_persian_grounding.py \
                             tests/assistant/test_persian.py \
                             tests/chat/test_streaming_persian.py -q
                       → 27 passed in 14.85s

Full non-integration   uv run pytest -m "not integration"
                       → 260 passed, 14 skipped, 40 deselected in 124.01s
                       (Sprint 2 baseline: 233 passed, 14 skipped, 36 deselected
                        → +27 new fast tests passing, +4 new integration tests deselected)

Ruff                   uv run ruff check . → All checks passed!
```

All pre-existing tests passed without modification or weakened assertions; no existing test file was touched.

## 9. Live OpenAI Validation

**Not executed.** The environment has no `backend/.env`, no `OPENAI_API_KEY` (checked `env`), and no ingested SEC corpus — the same blockers recorded in Sprints 0–2. The four live language-matrix tests in `tests/assistant/test_agent_persian_integration.py` (plus the pre-existing English integration tests) are ready and deselected by design; run `uv run pytest -m integration` once credentials + corpus exist. Nothing was invented: no live result is claimed anywhere in this report.

## 10. Regression Check

| Area | Status |
| --- | --- |
| Retrieval | **Untouched** — `retriever.py`, `keywords.py`, `queries.py`, `fusion.py`, `embeddings.py` unmodified; retrieval tests green |
| Embeddings | **Untouched** — `text-embedding-3-small`, 1536 dims, no reindexing |
| Database | **Untouched** — no migration, no schema change, no new columns |
| Supabase | **Untouched** — auth, REST persistence, RLS unmodified |
| OpenAI | **Provider/model unchanged** — `openai_chat_model` default `gpt-5.5`, grounding judge `gpt-4.1-mini`, both still OpenAI; no local inference, no new provider |
| PydanticAI | **Architecture unchanged** — same `Agent`, same 4 tools, same `GroundedAnswer` output type, same `UsageLimits`; only the `answer` field's description text changed |
| Citation | **Unchanged** — registry, verbatim excerpts from `document_chunks.text`, ASCII markers (now actually enforced), persistence |
| Grounding | **Fail-closed preserved** — validator rules identical except the stricter ASCII regex; judge criterion unchanged; retry ≤ 2 and `GROUNDING_FAILURE_MESSAGE` unchanged |
| Frontend | **Zero files modified** — existing frontend continues to render Persian answer text (Unicode JSON/SSE verified by round-trip test) |

## 11. Files Created

```text
backend/tests/grounding/test_persian_grounding.py
backend/tests/assistant/test_persian.py
backend/tests/chat/test_streaming_persian.py
backend/tests/assistant/test_agent_persian_integration.py
docs/sprint-3-persian-llm-grounding.md
docs/sprint-3-report.md                                   (this file)
```

## 12. Files Modified

```text
backend/app/assistant/instructions.md   additive ## Answer language section; 2 wording insertions
backend/app/assistant/outputs.py        answer field description → language-neutral (shape unchanged)
backend/app/grounding/validator.py      re.ASCII on marker regex; language-neutrality rule in judge prompt
```

Not modified (audit conclusion, per brief Parts 7/15/16/17): `assistant/tools.py`, `assistant/status.py`, `chat/streaming.py`, `chat/orchestrator.py`, all of `retrieval/`, database models/migrations, frontend.

## 13. Known Limitations

- Language selection is prompt/schema-description driven, not a classifier; pathologically ambiguous queries could still resolve either way (grounding still bounds the damage).
- Live Persian answer quality (fluency, terminology choices, cross-language citation behavior with real models) is unvalidated — no credentials/corpus in this environment.
- Pipeline status strings and the grounding-failure message remain English until the frontend localization sprint (SSE stage identifiers are stable protocol values; the limitation is documented in the design doc §8).
- Persian-digit markers are not repaired or rewritten; they fail validation closed and go through the existing retry/failure path.

## 14. Deferred Work

- **Persian UI / RTL / i18n** — frontend untouched; next natural sprint.
- **Localized status/error presentation** — needs the frontend i18n layer first (backend stage identifiers are already stable).
- **PDF/DOCX/OCR ingestion** — no code path exists; additive work for a later sprint.
- **Reranker** — Sprint 2 deferral stands.
- **Advanced morphology / suffix folding** — Sprint 1/2 deferral stands (`normalize.py`, needs evaluation).
- **Embedding evaluation** — untouched by design; `text-embedding-3-small` 1536-dim remains.

## 15. Recommendation for Sprint 4

1. **Run live validation as soon as credentials + corpus exist** (highest value, zero code): `uv run pytest -m integration` — the four new Persian language-matrix tests plus the existing English ones — then `scripts/smoke_assistant.py` with a Persian `QUERIES` entry (e.g. `"ریسک‌های Microsoft در سال 2024 چیست؟"`). Confirm Persian answers pass grounding with real models and inspect terminology quality.
2. **Frontend Persian/RTL sprint** (i18n layer, `dir` handling, Persian-capable font stack, bidi-safe citation chips, localized status/error presentation keyed off the stable stage identifiers) — the backend contract it needs is now in place and unchanged.
3. Only after live data: revisit Sprint 2's lexical-recall measurement and the deferred morphology/reranker decisions.
