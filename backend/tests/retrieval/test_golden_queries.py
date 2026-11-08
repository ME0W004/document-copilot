"""Golden-set harness: deterministic extraction contracts for every query.

Runs the full Persian/English/mixed golden set through the same preprocessing
the retriever uses (normalize → extract_fts_keywords) and asserts each
entry's documented contract. See golden_queries.py for the contract fields.
"""

from __future__ import annotations

from golden_queries import ALL_QUERIES, GoldenQuery
import pytest

from app.config import settings
from app.retrieval.keywords import extract_fts_keywords, tokenize
from app.text.normalize import normalize


def _keywords_for(case: GoldenQuery) -> str:
    return extract_fts_keywords(normalize(case.query))


@pytest.mark.parametrize("case", ALL_QUERIES, ids=lambda case: case.query)
def test_golden_query_contract(case: GoldenQuery) -> None:
    keywords = _keywords_for(case)

    assert keywords, f"keywords collapsed to empty for {case.query!r}"
    tokens = tokenize(keywords)
    if case.language != "english":
        # English fast-path queries pass through verbatim; the 'english' FTS
        # config removes their question words at query time, so the extractor
        # budget applies to the deterministic (persian/mixed) path only.
        assert len(tokens) <= settings.retrieval_fts_keyword_max
    for token in case.must_include:
        assert token in tokens, f"{token!r} missing from keywords {keywords!r}"
    for token in case.must_exclude:
        assert token not in tokens, f"{token!r} leaked into keywords {keywords!r}"


@pytest.mark.parametrize("case", ALL_QUERIES, ids=lambda case: case.query)
def test_golden_query_keywords_match_document_representation(case: GoldenQuery) -> None:
    if case.doc_text is None:
        pytest.skip("no fixture document for this query")
    if case.language == "english":
        pytest.skip("english fast path relies on query-time 'english' stopword removal")

    keywords = _keywords_for(case)

    doc_tokens = set(tokenize(normalize(case.doc_text)))
    missing = [token for token in tokenize(keywords) if token not in doc_tokens]
    assert not missing, (
        f"keywords {missing!r} absent from normalized document representation; "
        "the AND-semantics lexical leg could not match this fixture"
    )
