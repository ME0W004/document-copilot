"""Live-corpus retrieval smoke for the Persian golden set.

Requires live Supabase (migrated schema + ingested corpus) and OpenAI
credentials; deselected from the fast suite. Persian/mixed queries run
through the full hybrid pipeline against the SEC (English) corpus — the
semantic leg is expected to carry recall, the lexical leg may return few or
no hits for Persian-only terms, and neither may error.
"""

from __future__ import annotations

import pytest

from app.retrieval.retriever import DocumentRetriever
from golden_queries import MIXED_QUERIES, PERSIAN_QUERIES

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("case", PERSIAN_QUERIES + MIXED_QUERIES, ids=lambda c: c.query)
def test_persian_query_runs_through_hybrid_pipeline(case) -> None:
    retriever = DocumentRetriever()

    passages = retriever.search(case.query, top_k=5)

    assert isinstance(passages, list)
    for passage in passages:
        assert passage.text
        assert passage.fusion_score >= 0.0
