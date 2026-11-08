"""Keyword extraction for Postgres full-text search.

English queries keep the original strategy: short queries pass through
unchanged (the 'english' FTS config strips their question words), longer
ones are refined by OpenAI structured extraction merged with deterministic
English heuristics, and any LLM failure falls back to the deterministic
path.

Persian and mixed queries are handled by a deterministic Persian-aware
extractor and never touch the LLM: the SEC-tuned prompt and the old
ASCII-only heuristics were built for English and could drop Persian tokens.
Persian queries take this path even when short (no fast path) because
question words and particles must be removed — plainto_tsquery ANDs every
word, so one unmatched word zeroes out the lexical leg. The 'english' FTS
config passes Persian words through unchanged (no stemming of non-ASCII,
no Persian stopwords), so Persian matching comes from application-level
normalization plus this extractor's Persian stopword removal.
"""

from __future__ import annotations

import re

from openai import OpenAI
from pydantic import BaseModel, Field

from app.config import settings
from app.retrieval.types import SearchFilters
from app.text.normalize import normalize
from app.text.stopwords import is_stopword

_FILLER_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "across",
        "are",
        "as",
        "at",
        "be",
        "between",
        "by",
        "change",
        "changed",
        "describe",
        "describes",
        "described",
        "did",
        "do",
        "for",
        "from",
        "how",
        "in",
        "into",
        "is",
        "its",
        "of",
        "on",
        "or",
        "the",
        "their",
        "they",
        "this",
        "to",
        "was",
        "way",
        "what",
        "when",
        "where",
        "which",
        "who",
        "with",
    }
)

_LOW_VALUE_FTS_WORDS = frozenset(
    {
        "driver",
        "drivers",
        "describe",
        "described",
        "describes",
        "change",
        "changed",
        "across",
        "way",
        "ks",
        "k",
    }
)

_KNOWN_PHRASES = (
    "customer concentration",
    "data center",
    "revenue mix",
    "cloud capacity",
    "ai infrastructure",
)

_TICKER_COMPANY_PREFIXES: dict[str, str] = {
    "AAPL": "apple",
    "AMZN": "amazon",
    "GOOGL": "google",
    "MSFT": "microsoft",
    "NVDA": "nvidia",
}

_SYSTEM_PROMPT = """\
You extract search keywords for PostgreSQL full-text search over SEC filing chunks.

Rules:
- Return 3 to 5 terms. When joined with spaces, the total word count must be 5 or fewer \
(PostgreSQL ANDs every word — extra words cause zero matches).
- Prefer domain nouns and standard two-word SEC phrases (e.g. "data center", "revenue mix", \
"customer concentration"). Each phrase counts as two words toward the limit.
- Omit question filler and generic verbs (how, what, describe, change, drivers, across).
- Preserve product-name casing from the query (iPhone, Mac, iPad, Azure).
- When a ticker filter is provided, omit the company name from terms.
"""


class FtsKeywordExtraction(BaseModel):
    terms: list[str] = Field(
        min_length=1,
        description="3-5 search terms for full-text search",
    )


def _client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


def _token_count(query: str) -> int:
    return len(query.split())


def _normalize_terms(terms: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for term in terms:
        cleaned = term.strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)
    return normalized


def _is_company_token(token: str, filters: SearchFilters | None) -> bool:
    if filters is None or filters.ticker is None:
        return False
    prefix = _TICKER_COMPANY_PREFIXES.get(filters.ticker)
    if prefix is None:
        return False
    return token.casefold().startswith(prefix)


def _phrases_in_query(query: str) -> list[str]:
    lowered = query.casefold()
    found: list[str] = []
    for phrase in _KNOWN_PHRASES:
        start = lowered.find(phrase)
        if start == -1:
            continue
        found.append(query[start : start + len(phrase)])
    return found


def _capitalized_tokens(query: str, *, filters: SearchFilters | None) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9]*(?:'s)?", query)
    caps: list[str] = []
    for token in tokens:
        bare = token.removesuffix("'s")
        if bare.casefold() in _FILLER_WORDS:
            continue
        if bare.casefold() in _LOW_VALUE_FTS_WORDS:
            continue
        if _is_company_token(token, filters):
            continue
        if len(bare) <= 2:
            continue
        if bare[0].isupper() or re.fullmatch(r"i[A-Z][A-Za-z0-9]*", bare):
            caps.append(bare)
    return caps


def _apply_word_budget(words: list[str]) -> list[str]:
    maximum = settings.retrieval_fts_keyword_max
    seen: set[str] = set()
    kept: list[str] = []
    for word in words:
        for part in word.split():
            key = part.casefold()
            if key in seen:
                continue
            if key in _FILLER_WORDS or key in _LOW_VALUE_FTS_WORDS:
                continue
            seen.add(key)
            kept.append(part)
            if len(kept) >= maximum:
                return kept
    return kept


def _merge_fts_words(
    query: str,
    llm_terms: list[str],
    *,
    filters: SearchFilters | None,
) -> list[str]:
    caps = _capitalized_tokens(query, filters=filters)
    phrases = _phrases_in_query(query)
    llm_words = _apply_word_budget(_flatten_term_list(llm_terms))

    candidates: list[str] = []
    if len(caps) >= 3:
        candidates.extend(caps)
    else:
        candidates.extend(phrases)
        candidates.extend(caps)
    candidates.extend(llm_words)
    return _apply_word_budget(candidates)


def _flatten_term_list(terms: list[str]) -> list[str]:
    words: list[str] = []
    for term in terms:
        words.extend(term.split())
    return words


_ZWNJ = "\u200c"

# Arabic-script letters (Persian, Arabic cousins, presentation forms),
# excluding the block's punctuation (، ؛ ؟ ٪ ۔), digit families, and
# combining marks: punctuation and digits must separate tokens.
_ARABIC_LETTERS = (
    "\u0620-\u063a\u0641-\u064a\u066e-\u06d5\u06fa-\u06fc\u06ff"
    "\u0750-\u077f\u08a0-\u08ff"
    "\ufb50-\ufd3d\ufdf0-\ufdff\ufe70-\ufefc"
)

# English/number tokens keep internal hyphens and slashes (10-K, FY2024);
# Persian/Arabic-Indic digits are included so unnormalized input cannot lose
# them (normalize() folds them to ASCII afterwards). Persian tokens may carry
# internal ZWNJ (ریسک‌های) per the Sprint 1 normalization policy.
# plainto_tsquery and the generated search_vector are tokenized by the same
# Postgres parser, so ZWNJ tokens are split identically on both sides.
_TOKEN_RE = re.compile(
    rf"[0-9A-Za-z\u0660-\u0669\u06f0-\u06f9][0-9A-Za-z\-/\u0660-\u0669\u06f0-\u06f9]*"
    rf"|[{_ARABIC_LETTERS}](?:[{_ARABIC_LETTERS}{_ZWNJ}]*[{_ARABIC_LETTERS}])?"
)


def tokenize(text: str) -> list[str]:
    """Deterministic lexical tokens: Persian words, English words, numbers."""
    return _TOKEN_RE.findall(text)


def _contains_arabic_script(text: str) -> bool:
    return bool(re.search(rf"[{_ARABIC_LETTERS}]", text))


def _deterministic_persian_keywords(
    query: str,
    *,
    filters: SearchFilters | None,
) -> str:
    """Persian/mixed extraction: order-preserving, stopword-filtered tokens.

    Tokens are normalized so keyword spelling always matches the normalized
    search_text representation (Arabic yeh/kaf variants, digit families,
    diacritics), even when the caller has not pre-normalized the query.
    """
    kept: list[str] = []
    seen: set[str] = set()
    for raw_token in tokenize(query):
        token = normalize(raw_token)
        if not token:
            continue
        key = token.casefold()
        if key in seen:
            continue
        if key in _FILLER_WORDS or key in _LOW_VALUE_FTS_WORDS:
            continue
        if is_stopword(token):
            continue
        if _is_company_token(token, filters):
            continue
        seen.add(key)
        kept.append(token)
    if not kept:
        return query.strip()
    return " ".join(kept[: settings.retrieval_fts_keyword_max])


def _deterministic_fallback(query: str, *, filters: SearchFilters | None) -> str:
    tokens = tokenize(query)
    kept: list[str] = []
    for token in tokens:
        if token.casefold() in _FILLER_WORDS:
            continue
        if is_stopword(token):
            continue
        if _is_company_token(token, filters):
            continue
        kept.append(token)
    words = _merge_fts_words(query, kept, filters=filters)
    if not words:
        return query.strip()
    return " ".join(words)


def _build_user_message(query: str, filters: SearchFilters | None) -> str:
    parts = [f"Query: {query}"]
    if filters is not None and filters.ticker is not None:
        parts.append(f"Ticker filter: {filters.ticker} (omit company name from terms)")
    if filters is not None and filters.form is not None:
        parts.append(f"Form filter: {filters.form}")
    return "\n".join(parts)


def extract_fts_keywords(
    query: str,
    *,
    filters: SearchFilters | None = None,
) -> str:
    """Return a space-joined keyword string for plainto_tsquery."""
    stripped = query.strip()
    if not stripped:
        return stripped

    if _contains_arabic_script(stripped):
        return _deterministic_persian_keywords(stripped, filters=filters)

    if _token_count(stripped) <= settings.retrieval_fts_keyword_fast_path_tokens:
        return stripped

    try:
        response = _client().chat.completions.parse(
            model=settings.retrieval_fts_keyword_model,
            temperature=0,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_message(stripped, filters)},
            ],
            response_format=FtsKeywordExtraction,
        )
        parsed = response.choices[0].message.parsed
        if parsed is None:
            return _deterministic_fallback(stripped, filters=filters)

        words = _merge_fts_words(stripped, _normalize_terms(parsed.terms), filters=filters)
        if len(words) < settings.retrieval_fts_keyword_min:
            return _deterministic_fallback(stripped, filters=filters)
        return " ".join(words)
    except Exception:
        return _deterministic_fallback(stripped, filters=filters)
