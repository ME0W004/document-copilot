"""Search-representation tests: normalized documents meet normalized queries.

Sprint 2's lexical layer works because query keywords and the chunk
``search_text`` representation pass through the same ``normalize()``. These
tests pin the equivalence classes that guarantee a query spelled with
Arabic-variant codepoints, Persian/Arabic-Indic digits, diacritics, or ZWNJ
variants still matches the normalized document representation. No database
is involved: the contract is application-level normalization plus the
deterministic extractor (the same Postgres parser tokenizes both sides, so
equal normalized strings always produce equal lexemes).
"""

from __future__ import annotations

import pytest

from app.text.normalize import normalize
from app.text.stopwords import is_stopword


@pytest.mark.parametrize(
    ("variant", "canonical"),
    [
        ("\u064a\u06a9", "\u06cc\u06a9"),  # يک (Arabic yeh) / یک (Persian yeh)
        ("شركت", "شرکت"),  # Arabic kaf / keheh
        ("رﺳﻴﺪ", "رسید"),  # presentation forms / standard letters
        ("۱۴۰۳", "1403"),  # Persian digits / ASCII
        ("١٤٠٣", "1403"),  # Arabic-Indic digits / ASCII
        ("مُحَمَّد", "محمد"),  # diacritics stripped
        ("کتــــاب", "کتاب"),  # tatweel stripped
    ],
)
def test_variant_and_canonical_normalize_identically(
    variant: str, canonical: str
) -> None:
    assert normalize(variant) == normalize(canonical)


def test_zwnj_variants_converge() -> None:
    assert normalize("می‌‌روم") == normalize("می‌روم")  # doubled ZWNJ collapses
    assert normalize("می‌ رود") == normalize("می رود")  # boundary ZWNJ dropped
    assert normalize("هم‌کاران") == "هم‌کاران"  # meaningful ZWNJ preserved


def test_digits_around_words_fold_without_damage() -> None:
    assert normalize("FY۱۴۰۳ و 10-K سال ٢٠٢٤") == "FY1403 و 10-K سال 2024"


def test_mixed_persian_english_preserved_verbatim() -> None:
    normalized = normalize("ریسک‌های AWS در سال ۱۴۰۳")

    assert "AWS" in normalized
    assert "ریسک‌های" in normalized
    assert "1403" in normalized


def test_stopword_lookup_normalizes_raw_variants() -> None:
    assert is_stopword("\u064a\u06a9")  # يک with Arabic yeh
    assert is_stopword("اَز")  # اَز with fatha
    assert not is_stopword("شرکت")
    assert not is_stopword("1403")


def test_normalized_equivalent_query_matches_document_representation() -> None:
    """The Part 20 requirement: codepoint/digit families must not break matching.

    Document and query spell the shared words with different Arabic codepoints
    (Arabic kaf in the query) and different digit families (mixed
    Persian/Arabic-Indic digits in the document). After normalization the
    query's extracted keywords are a subset of the document's tokens, which is
    the condition the AND-semantics plainto_tsquery leg needs for a match.
    """
    from app.retrieval.keywords import extract_fts_keywords, tokenize

    document = "شركت در سال ۱۴٠٣ رشدی بزرگ داشت."
    query = "شرکت در سال 1403 چه رشدی داشت؟"

    doc_tokens = set(tokenize(normalize(document)))
    keywords = extract_fts_keywords(normalize(query))

    assert {"شرکت", "سال", "1403"} <= doc_tokens
    assert set(tokenize(keywords)) <= doc_tokens
