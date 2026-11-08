# Persian Text Normalization

**Sprint 1 deliverable — Persian Language Core.**
Implementation: `backend/app/text/normalize.py`, `backend/app/text/stopwords.py`.
Tests: `backend/tests/text/test_normalize.py`, `backend/tests/text/test_stopwords.py`.

> Sprint 1 establishes the canonical normalization layer. It does not yet change retrieval, ingestion, database schema, embeddings, or UI.

---

## 1. Why normalization exists

Persian text reaches the system through many channels (user queries, HTML filings, PDF/OCR output, pasted documents), and the same word can be spelled with different Unicode codepoints:

- Arabic letter variants for Persian letters (`ي` U+064A vs `ی` U+06CC; `ك` U+0643 vs `ک` U+06A9),
- three digit families (Persian `۱۴۰۳`, Arabic-Indic `١٤٠٣`, ASCII `1403`),
- optional diacritics (`مُحَمَّد` vs `محمد`),
- ZWNJ (`U+200C`) present, missing, doubled, or adjacent to spaces,
- Arabic presentation forms (U+FB50–U+FDFF, U+FE70–U+FEFF) from PDFs,
- kashida/tatweel stretching, bidi control characters, and irregular whitespace.

Without one canonical folding, identical words compare unequal and lexical retrieval cannot match them. Postgres ships no Persian text-search configuration, and the current `'english'` FTS stack performs none of the above — so the folding must happen in application code before text reaches any search representation. This module is the **single source of truth** for that folding; later sprints must not grow private copies.

## 2. What transformations are currently applied

`normalize(text: str) -> str` runs seven stages in a fixed order. Every stage is idempotent, so `normalize(normalize(text)) == normalize(text)` (property-tested over all fixtures).

| Stage | Function | Transformation |
| --- | --- | --- |
| 1 | `normalize_codepoints` | Arabic presentation forms (U+FB50–U+FDFF, U+FE70–U+FEFF) → standard letters via NFKC, **scoped to those blocks only**. Then Arabic letter variants fold to Persian: `ي`→`ی`, `ى`→`ی`, `ك`→`ک`. |
| 2 | `normalize_digits` | Persian `۰-۹` (U+06F0–06F9) and Arabic-Indic `٠-٩` (U+0660–0669) → ASCII `0-9`. |
| 3 | `strip_diacritics` | Removes combining marks (Unicode category Mn) in: U+0610–061A (annotation signs), U+064B–065F (tashkeel: fatha, damma, kasra, shadda, sukun, tanwin, hamza marks), U+0670 (superscript alef), U+06D6–06DC, U+06DF–06E8, U+06EA–06ED (Quranic marks); plus tatweel U+0640. |
| 4 | (inline) | Removes bidi formatting controls: LRM/RLM (U+200E/200F), embedding controls (U+202A–202E), isolates (U+2066–2069). Rendering-only, no word identity. |
| 5 | `normalize_zwnj` | ZWNJ cleanup — see §4. |
| 6 | `normalize_whitespace` | `\r\n?` and U+2028/2029 → `\n`; every other whitespace (tabs, NBSP, en/em spaces) → single space; spaces hugging newlines removed; newline runs capped at two (one blank line); edges stripped. |

## 3. What transformations are intentionally NOT applied

- **No stemming / suffix folding** (`ها`, `های`, `تر`, `ترین`) — belongs to retrieval evaluation, Sprint 2+.
- **No morphological reconstruction** — no prefix/suffix splitting, no ezafe handling.
- **No hamza folding** — `أ` `إ` `ؤ` `ئ` stay distinct: they distinguish spellings in Arabic loanwords.
- **No `ة`→`ه`, `ۀ`→`ه`, `ه`→`ة` folding** — lossy and meaning-adjacent.
- **No `آ`→`ا` folding** — madda is a distinct Persian letter (`آمدن` ≠ `امدن`).
- **No punctuation rewriting** — `،` `؛` `؟` and ASCII punctuation pass through untouched.
- **No ZWJ removal** (U+200D) — meaningful in emoji sequences and other scripts.
- **No transliteration or translation** — English terms embedded in Persian are never altered.
- **No full-width/CJK-style broad NFKC** — NFKC is applied only to the Arabic presentation-form blocks, never to the whole string.
- **No Persian tokenizer** — tokenization is deferred until keyword extraction needs it.

## 4. ZWNJ policy

ZWNJ (`U+200C`) controls cursive joining and is *linguistically meaningful* in Persian: `می‌روم` (I go) vs `می روم`, `هم‌کاران` (colleagues) vs `همکاران`. The policy is deliberately conservative:

1. **Preserved** when it sits strictly between two Arabic-script letters (category `Lo` in the Arabic blocks) — exactly the positions where it prevents joining: `می‌روم`, `هم‌کاران`.
2. **Dropped** when adjacent to whitespace, punctuation, digits, Latin text, or a string boundary — there is nothing to un-join, so the mark is redundant noise: `می‌ رود` → `می رود`, `abc‌def` → `abcdef`.
3. **Repeated ZWNJ runs collapse** to a single ZWNJ: `می‌‌روم` → `می‌روم`.
4. **Never rewritten to a space** and **never deleted wholesale**.
5. A **single stray ZWNJ inside a word** (`می‌ر‌وم`) is preserved: distinguishing it from a legitimate boundary requires morphological analysis that is out of Sprint 1 scope. The behavior is deterministic and idempotent either way.

Consequence: ZWNJ distinguishes tokens in the normalized representation, so downstream keyword/token stages must treat ZWNJ as part of the token (not as a separator) unless they deliberately decide otherwise.

## 5. Digit policy

All three digit families fold to **ASCII** (`۱۴۰۳`, `١٤٠٣`, `1403` → `1403`). ASCII is the canonical form because:

- it is script-neutral and sorts/compares identically everywhere,
- it matches how financial figures and identifiers (10-K, FY2024, accession numbers) already appear in the corpus,
- the alternative (folding to Persian) would break every existing English/SEC match.

Characters *around* numbers are never modified: `FY۱۴۰۳` → `FY1403`, not `FY۱۴۰۳` → `FY۲۰۲۴`-style rewrites.

## 6. Original text vs search text

There are two representations, and Sprint 1 only introduces the *function* that derives the second:

```text
document_chunks.text
    = original canonical text
    = used for citations / excerpts / grounding / source viewer

normalized/search representation
    = derived from original text via normalize()
    = used only for retrieval/search (not yet materialized)
```

Rules that later sprints must keep:

- `normalize()` never receives a write path to `document_chunks.text`. Nothing in Sprint 1 calls it in the app at all — it is a stable, tested library.
- Verbatim excerpts, grounding validation, and the citation viewer continue to use the original text.
- When a search representation is added (Sprint 2), it lives **alongside** the canonical column (e.g. a generated/derived column or index), never in place of it.

## 7. Stopword policy

`backend/app/text/stopwords.py` exposes `PERSIAN_STOPWORDS: frozenset[str]` and `is_stopword(token: str) -> bool`.

- The set is **small, explicit, and conservative**: the classic function words (`و در به از که را با برای این آن یک تا بر یا اما اگر هم نیز`), minimal copulas/auxiliaries (`است بود شد شده باشد هستند بودند شود`), pronouns (`من ما تو شما او وی`), and a few high-frequency connectives (`هر همه چون پس`). 36 entries total.
- **No giant internet list was copied.** The set will only grow through Sprint 2 retrieval evaluation evidence, not wholesale import.
- Entries are stored in **normalized spelling**; `is_stopword` normalizes its input first, so raw tokens (`يک`, `اَز`, `" در "`) are handled correctly.
- No LLM dependency, no network, no NLP framework — pure stdlib.

## 8. Examples

| Input | `normalize()` output | What happened |
| --- | --- | --- |
| `يک شركت` | `یک شرکت` | Arabic yeh/kaf → Persian |
| `شركت Apple كه در FY۱۴۰۳` | `شرکت Apple که در FY1403` | letter folding + digit folding; English untouched |
| `مُحَمَّد` | `محمد` | diacritics stripped |
| `کتــــاب` (with tatweel) | `کتاب` | kashida removed |
| `می‌‌روم` (double ZWNJ) | `می‌روم` | run collapsed |
| `می‌ رود` | `می رود` | ZWNJ next to space dropped |
| `  متن   اول\n\nمتن دوم  ` | `متن اول\n\nمتن دوم` | whitespace collapsed, paragraph kept |
| `ﻻ` (U+FEFB) | `لا` | presentation form decomposed |
| `OpenAI API در سیستم` | `OpenAI API در سیستم` | nothing to change — stable |

## 9. Future integration points

- **Sprint 2 (Persian retrieval):** normalize query text before keyword extraction/FTS; derive a normalized search representation for chunks (new column/index — a schema change with its own migration); extend `keywords.py` (currently ASCII-only) with Persian-aware extraction using `PERSIAN_STOPWORDS`.
- **Ingestion:** optionally store a normalized shadow of chunk text (again, alongside — never replacing — the canonical `text`).
- **Persian FTS:** Postgres has no Persian config; a `simple`-config + pre-normalized text approach or a custom dictionary will build on this module.
- **OCR cleanup:** the same stages give OCR output a deterministic baseline cleanup before ingestion.

Related baseline references: `docs/baseline.md` §8 (retrieval defects K7), `docs/local-persian-migration-audit.md` §6.2.
