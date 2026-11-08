# Sprint 3 — Persian LLM + Grounding

**Deliverable:** language-aware agent instructions, structured-output schema, and grounding judge — Persian questions get Persian answers, English questions get English answers, and Persian evidence remains fully citable — with every grounding and citation guarantee preserved.
**Companion report:** [sprint-3-report.md](sprint-3-report.md) (exact files, commands, results).
**Prior sprints:** [baseline.md](baseline.md) · [persian-text-normalization.md](persian-text-normalization.md) · [sprint-2-persian-retrieval.md](sprint-2-persian-retrieval.md).

> Sprint 3 does not replace the OpenAI model, embedding model, or retrieval architecture.
>
> `document_chunks.text` remains the canonical citation source.

---

## 1. Existing LLM/agent architecture (the language-relevant map)

The chat turn is unchanged end to end:

```text
POST /chat/stream → chat/orchestrator.py:run_turn
    → assistant/agent.py:run_document_agent        (PydanticAI run_sync in a thread)
        → Agent(instructions=INSTRUCTIONS, tools=[4 tools], output_type=GroundedAnswer)
            → tools (search_filings / read_chunks / read_chunk / read_surrounding_chunks)
                → DocumentRetriever.search (Sprint 2: normalizes query; both legs + RRF unchanged)
            → GroundedAnswer (structured output)
    → prune_unreferenced_citations
    → GroundingValidator.validate (structural checks → TurnRegistry allowlist → LLM judge)
    → retry ≤ 2 attempts → stream (word-by-word SSE) → persist
```

Language behavior reaches the model through **four channels** — instructions.md is *not* the only one:

| # | Channel | File | Sprint 3 finding |
| --- | --- | --- | --- |
| 1 | System prompt (`Agent(instructions=…)`) | `assistant/instructions.md` (read in `assistant/agent.py:22-23`) | English/SEC-only; needed the language policy |
| 2 | Tool docstrings → PydanticAI tool definitions | `assistant/tools.py` | Already language-neutral ("Search SEC filings with hybrid retrieval…"); no query-language assumption. **Unchanged.** |
| 3 | Output-model field descriptions → structured-output JSON schema | `assistant/outputs.py` | **Defect:** `answer` was described as "Plain-English answer", biasing the schema toward English on every request |
| 4 | Grounding judge system prompt | `grounding/validator.py` | Language-neutral in substance but had no explicit cross-language rule; risk of language-mismatch false negatives |

Supporting layers audited for Persian compatibility:

- **`assistant/status.py` / `chat/orchestrator.py` status messages** — stage identifiers (`analyzing`, `searching`, `reading`, `verifying`, `retrying`, `streaming`) are stable protocol values; the display strings ("Analyzing your question…") are hard-coded English. Kept unchanged (see §8).
- **`chat/streaming.py`** — `_text_events` splits on spaces (Persian is space-separated; ZWNJ never splits) and `json.dumps` (default `ensure_ascii`) emits `\uXXXX` escapes that are valid JSON and decode to identical strings — wire-safe for Persian. `GROUNDING_FAILURE_MESSAGE` unchanged. **Unchanged.**
- **`chat/messages.py` / `schemas/chat.py` / persistence** — pass-through of Unicode strings into JSONB; nothing language-specific. **Unchanged.**
- **`retrieval/*`** — out of scope (Sprint 2); untouched.

## 2. Persian language policy

- A Persian question (including a mixed question dominated by Persian) is answered in natural Persian prose with Persian punctuation, preserving Markdown structure (lists, tables, emphasis).
- Company names, tickers, product names, filing identifiers (`10-K`, `Item 7`, `MD&A`), and technical financial terms stay in English whenever translating or transliterating them would reduce accuracy or readability; technical identifiers are never transliterated.
- Citation markers in Persian answers use **ASCII digits only** (`[1]`, `[2]`) — never `[۱]`.
- Persian answers may cite English passages; excerpts and source metadata always remain in the source's original language.

## 3. English language policy

- An English question gets an English answer; nothing about the Persian additions changes English behavior (the policy is "same language as the user's question" — English questions resolve to English regardless of source language or UI language).
- English answers may cite Persian passages; excerpts stay verbatim Persian.

## 4. Mixed-language policy

- Mixed Persian/English questions (e.g. `ریسک‌های Microsoft در سال 2024 چیست؟`) are answered primarily in the dominant language of the question (per the brief's test matrix: "Mixed Persian/English → Primarily Persian") with technical terms preserved naturally.
- There is **no translation layer**: the raw query reaches the model verbatim (retrieval normalizes internally, Sprint 2), the model reasons over verbatim source passages in whatever language they are, and the answer language is selected only by the instructions policy.

## 5. Prompt/instruction changes

**`backend/app/assistant/instructions.md`** — additive only; the product contract, corpus scope, tool usage, and output format rules are byte-identical except two explicitly listed insertions:

1. New `## Answer language` section between *Product contract* and *Corpus scope*, containing the §2–§4 policies above plus the ASCII-marker rule.
2. *Tool usage* step 1: one added sentence — "Search queries may be in any language."
3. *Output format* closing paragraph: excerpts must be copied "in the chunk's original language" and `translate` joins the forbidden rewrites (rewrite/merge/clean-up already forbidden).

**`backend/app/assistant/outputs.py`** — the `GroundedAnswer.answer` field description changed from `"Plain-English answer with [n] citation markers"` to `"Answer in the user's language with ASCII [n] citation markers"`. This description is part of the structured-output JSON schema PydanticAI sends with every request, so it directly conditions model behavior. Schema **shape** is unchanged (same fields, same types, same required list — pinned by test).

## 6. Grounding changes

Two changes, both proven necessary by inspection, both strictly fail-closed:

1. **Citation-marker regex is now ASCII-only** (`grounding/validator.py`): `re.compile(r"\[(\d+)\]", re.ASCII)`. Python's Unicode `\d` matches every `Nd` digit — including Persian `۱` (U+06F1) and Arabic-Indic `١` (U+0661) — and `int("۱") == 1`, so the old pattern **accepted** Persian-digit markers, while the documented contract (baseline §9 rule 5: "ASCII digits on both sides") and the frontend (`AssistantMarkdown.tsx` uses JavaScript `\d`, ASCII-only) reject them. A Persian answer citing `[۱]` would have passed validation and streamed to a frontend that cannot render it as a citation. The fix enforces the existing contract — validation becomes stricter, never weaker.
2. **Judge prompt is explicitly language-neutral** (`_GROUNDING_JUDGE_SYSTEM_PROMPT`): added rule — "The answer, excerpt, and source_text may be in any language, including Persian, English, or a mix. Judge support regardless of language; never mark a citation unsupported merely because the answer and source_text are in different languages, and do not translate source_text." This prevents cross-language false negatives only; the support criterion, injection-safety rule, and fail-closed behavior are untouched.

Everything else in the validator was audited and left unchanged: excerpt handling passes `citation.excerpt` and `passage.text` through to the judge **verbatim with no normalization** (verified by a strict-verbatim test), indices/markers logic is integer-based, Pydantic v2 parsing and JSON serialization are Unicode-safe.

## 7. Citation preservation rules (unchanged)

- `TurnRegistry` remains the sole citation allowlist.
- Excerpts must be verbatim substrings of the canonical `document_chunks.text` — never `search_text`, never normalized text.
- `[n]` markers ↔ `citation_index` exact match, unique, 1-based, contiguous, ASCII digits.
- `insufficient_evidence = true` ⇒ zero citations; grounded answers ⇒ ≥ 1 citation.
- One retry, then the controlled `GROUNDING_FAILURE_MESSAGE`; nothing unverifiable is streamed.

## 8. Status and error messages (decision recorded)

Per the brief (Parts 15–16): internal stage identifiers stay stable and the SSE event contract is unchanged; the English display strings (`status.py`, `orchestrator.py`) and `GROUNDING_FAILURE_MESSAGE` remain as-is until the frontend localization sprint. No second language field was added to SSE events. The backend already returns valid Unicode Persian in answer/citation payloads, so the existing frontend renders Persian answer text without changes. **Limitation:** until frontend i18n lands, Persian-asking users still see English pipeline status strings and the English grounding-failure message.

## 9. Persian test strategy

- **Grounding units** (`tests/grounding/test_persian_grounding.py`, 18 tests): the brief's Cases A–J plus Arabic-Indic-marker rejection, Persian-digit markers not pruned as referenced, verbatim pass-through of special-character excerpts (Arabic/Persian yeh–kaf, ZWNJ, Persian + Arabic-Indic digits, Persian punctuation, embedded English) to the judge, a strict-verbatim judge proving no normalization happens inside citation validation, and Persian prune behavior.
- **Assistant units** (`tests/assistant/test_persian.py`, 9 tests): the instructions language-policy contract (the prompt is the product), technical-terms and ASCII-marker policy, existing safety rules still present, schema description language-neutral, `GroundedAnswer` schema shape pinned unchanged, and Persian tool-result formatting (verbatim passthrough + 800-char truncation).
- **Chat units** (`tests/chat/test_streaming_persian.py`, 1 test): a Persian answer with ZWNJ + citation streams through the AI SDK SSE format and JSON-round-trips to the exact original text.
- **Live integration** (`tests/assistant/test_agent_persian_integration.py`, 4 tests, `@pytest.mark.integration`): Persian query → Persian grounded answer; English query → English answer; mixed query → primarily Persian; Persian underspecified question → zero citations. Script-detection regex `[\u0600-\u06FF]`; no exact-prose assertions.

## 10. Live validation status

**Not executed.** No `backend/.env`, no `OPENAI_API_KEY`, and no ingested corpus exist in this environment (same as Sprints 0–2). All offline tests were run; the integration files exist and are deselected by design until credentials + corpus are available.

## 11. Known limitations

- Language selection is prompt-driven (instructions + schema description), not a classifier — a pathologically ambiguous query could still get either language; grounding still bounds the damage.
- Persian answer quality (fluency, terminology) is unvalidated against live models (no credentials).
- Status/error display strings remain English until the frontend i18n sprint (§8).
- Persian-digit markers inside the answer body are not rewritten or repaired; the validator simply fails them closed and the orchestrator retries/fails per the existing contract.

## 12. Deferred work

- Persian UI, RTL, i18n, localized status/error presentation (frontend sprint).
- PDF/DOCX/OCR ingestion paths (no code path exists).
- Reranker; advanced Persian morphology; embedding evaluation (Sprint 2 deferrals, unchanged).
- Live corpus validation of Persian end-to-end behavior (blocked on credentials + corpus).
