"""Retrieval orchestration tests for Persian query normalization (Sprint 2)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import UUID

from app.database.models import DocumentChunk, SourceDocument
from app.retrieval.retriever import DocumentRetriever
from app.retrieval.types import RankedChunkHit, SearchFilters
from app.text.normalize import normalize

ID_A = UUID("00000000-0000-0000-0000-000000000001")
ID_B = UUID("00000000-0000-0000-0000-000000000002")
DOC_ID = UUID("00000000-0000-0000-0000-000000000100")

# Deliberately unnormalized: Arabic kaf, Arabic yeh, Persian digits.
RAW_QUERY = "ریسك‌های Microsoft در سال ۲۰۲۴ چیست؟"


def _document() -> SourceDocument:
    from datetime import date

    return SourceDocument(
        id=DOC_ID,
        ticker="MSFT",
        cik="0000789019",
        company_name="Microsoft Inc.",
        form="10-K",
        filing_date=date(2024, 10, 31),
        fiscal_year=2024,
        accession_number="0000789019-24-000123",
        primary_document="msft-10k.htm",
        source_url="https://example.com/msft",
    )


@patch("app.retrieval.retriever.get_surrounding_chunks")
@patch("app.retrieval.retriever.get_chunks_by_ids")
@patch("app.retrieval.retriever.full_text_search")
@patch("app.retrieval.retriever.semantic_search")
@patch("app.retrieval.retriever.extract_fts_keywords")
@patch("app.retrieval.retriever.embed_query")
def test_search_normalizes_persian_query_for_both_legs(
    mock_embed_query: MagicMock,
    mock_extract_fts_keywords: MagicMock,
    mock_semantic_search: MagicMock,
    mock_full_text_search: MagicMock,
    mock_get_chunks_by_ids: MagicMock,
    mock_get_surrounding_chunks: MagicMock,
) -> None:
    mock_embed_query.return_value = [0.1] * 3
    mock_extract_fts_keywords.return_value = "ریسک‌های Microsoft 2024"
    mock_semantic_search.return_value = [
        RankedChunkHit(chunk_id=ID_A, rank=1, score=0.9)
    ]
    mock_full_text_search.return_value = [
        RankedChunkHit(chunk_id=ID_B, rank=1, score=0.7)
    ]
    document = _document()
    chunk_a = DocumentChunk(
        id=ID_A,
        document_id=DOC_ID,
        chunk_index=0,
        page=None,
        section=None,
        text="ریسک‌های Microsoft",
        chunk_metadata={},
        document=document,
    )
    chunk_b = DocumentChunk(
        id=ID_B,
        document_id=DOC_ID,
        chunk_index=1,
        page=None,
        section=None,
        text="cloud revenue",
        chunk_metadata={},
        document=document,
    )
    mock_get_chunks_by_ids.return_value = {ID_A: chunk_a, ID_B: chunk_b}
    mock_get_surrounding_chunks.return_value = []

    retriever = DocumentRetriever()
    passages = retriever.search(
        RAW_QUERY,
        filters=SearchFilters(ticker="MSFT"),
        candidate_k=50,
        top_k=2,
        session=MagicMock(),
    )

    assert len(passages) == 2
    expected = normalize(RAW_QUERY)
    assert expected != RAW_QUERY  # the fixture really contains variant codepoints
    mock_embed_query.assert_called_once_with(expected)
    mock_extract_fts_keywords.assert_called_once_with(
        expected, filters=SearchFilters(ticker="MSFT")
    )


@patch("app.retrieval.retriever.get_surrounding_chunks")
@patch("app.retrieval.retriever.get_chunks_by_ids")
@patch("app.retrieval.retriever.full_text_search")
@patch("app.retrieval.retriever.semantic_search")
@patch("app.retrieval.retriever.extract_fts_keywords")
@patch("app.retrieval.retriever.embed_query")
def test_persian_keywords_reach_lexical_leg_with_unchanged_semantics(
    mock_embed_query: MagicMock,
    mock_extract_fts_keywords: MagicMock,
    mock_semantic_search: MagicMock,
    mock_full_text_search: MagicMock,
    mock_get_chunks_by_ids: MagicMock,
    mock_get_surrounding_chunks: MagicMock,
) -> None:
    mock_embed_query.return_value = [0.1] * 3
    mock_extract_fts_keywords.return_value = "ریسک‌های Microsoft 2024"
    mock_semantic_search.return_value = [
        RankedChunkHit(chunk_id=ID_A, rank=1, score=0.9)
    ]
    mock_full_text_search.return_value = []
    document = _document()
    chunk_a = DocumentChunk(
        id=ID_A,
        document_id=DOC_ID,
        chunk_index=0,
        page=None,
        section=None,
        text="ریسک‌های Microsoft",
        chunk_metadata={},
        document=document,
    )
    mock_get_chunks_by_ids.return_value = {ID_A: chunk_a}
    mock_get_surrounding_chunks.return_value = []

    retriever = DocumentRetriever()
    passages = retriever.search(
        RAW_QUERY,
        filters=SearchFilters(ticker="MSFT"),
        candidate_k=50,
        top_k=1,
        session=MagicMock(),
    )

    assert len(passages) == 1
    assert passages[0].chunk_id == ID_A

    # Both legs ran with unchanged candidate/limit semantics.
    mock_semantic_search.assert_called_once()
    assert mock_semantic_search.call_args.kwargs["limit"] == 50
    assert mock_semantic_search.call_args.kwargs["filters"] == SearchFilters(ticker="MSFT")
    mock_full_text_search.assert_called_once()
    assert mock_full_text_search.call_args.args[1] == "ریسک‌های Microsoft 2024"
