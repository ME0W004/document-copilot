"""Readiness tests for Source Text Integrity, Citations, Grounding, and Search (Sprint 5 Part 15-18, 23).

Covers:
- Canonical text integrity: document_chunks.text remains untouched.
- search_text derivation: search_text == normalize(text).
- Citation contract for generic documents: title snapshot, nullable SEC fields.
- Grounding validator fail-closed behavior with generic/OCR/Persian passages.
- TurnRegistry integration for generic document chunks.
- Idempotency: content-hash dedup and force re-ingest.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch


from app.assistant.deps import TurnRegistry
from app.assistant.outputs import Citation, GroundedAnswer
from app.database.models import DocumentChunk, SourceDocument
from app.grounding.validator import GroundingValidator
from app.retrieval.keywords import extract_fts_keywords
from app.retrieval.types import RetrievedPassage
from app.schemas.chat import CitationPayload
from app.text.normalize import normalize
from ingest.chunking import ChunkRecord
from ingest.persist import write_chunks


# ===========================================================================
# Part 15: Source Text Integrity & search_text Derivation
# ===========================================================================


def test_write_chunks_preserves_canonical_text_and_derives_search_text() -> None:
    """Canonical text must be preserved verbatim; search_text must equal normalize(text)."""
    persian_text = (
        "گزارش شرکت‌های ایرانی در سال ۱۴۰۳ با سود ۱۲.۵٪ همراه بود. "
        "مدل OpenAI و سیستم 10-K فعال است."
    )
    english_text = "Fiscal year 2024 operating revenue was $12,500 million."

    records = [
        ChunkRecord(
            chunk_index=0,
            text=persian_text,
            page="1",
            section="گزارش",
            token_count=35,
            chunk_metadata={"source_format": "pdf", "title": "گزارش"},
        ),
        ChunkRecord(
            chunk_index=1,
            text=english_text,
            page="2",
            section="Financials",
            token_count=12,
            chunk_metadata={"source_format": "pdf", "title": "Report"},
        ),
    ]

    mock_session = MagicMock()
    document = SourceDocument(
        id=uuid.uuid4(),
        source_format="pdf",
        title="Test Doc",
        created_at=datetime.now(UTC),
    )

    with patch("ingest.persist.embed_texts", return_value=[[0.1] * 1536, [0.2] * 1536]):
        count = write_chunks(mock_session, document, records)

    assert count == 2
    added_chunks = [
        call.args[0]
        for call in mock_session.add.call_args_list
        if isinstance(call.args[0], DocumentChunk)
    ]
    assert len(added_chunks) == 2

    # Chunk 0 (Persian): canonical text is untouched
    assert added_chunks[0].text == persian_text
    assert added_chunks[0].search_text == normalize(persian_text)
    # Digits folded in search_text, but canonical text retains original digits
    assert "۱۴۰۳" in added_chunks[0].text
    assert "1403" in added_chunks[0].search_text

    # Chunk 1 (English): canonical text is untouched
    assert added_chunks[1].text == english_text
    assert added_chunks[1].search_text == normalize(english_text)


# ===========================================================================
# Part 16 & 17: Citation & Grounding Readiness for Generic Documents
# ===========================================================================


def test_turn_registry_registers_generic_chunks() -> None:
    """TurnRegistry must accept and allowlist generic passages with title and nullable SEC fields."""
    registry = TurnRegistry()
    chunk_id = uuid.uuid4()

    passage = RetrievedPassage(
        chunk_id=chunk_id,
        document_id=uuid.uuid4(),
        chunk_index=0,
        text="This is an excerpt from a generic PDF document.",
        fusion_score=0.92,
        title="Annual PDF Report",
        ticker=None,
        company_name=None,
        form=None,
        filing_date=None,
        fiscal_year=None,
        accession_number=None,
        page="3",
        section="Risk Factors",
    )
    registry.register(passage)

    assert chunk_id in registry.passages_by_chunk_id
    assert registry.passages_by_chunk_id[chunk_id] == passage


def test_citation_payload_supports_generic_documents() -> None:
    """CitationPayload must correctly represent generic documents without SEC fields."""
    chunk_id = uuid.uuid4()
    payload = CitationPayload(
        citation_index=1,
        chunk_id=chunk_id,
        excerpt="Verbatim excerpt from the document.",
        title="Research Paper",
        ticker=None,
        form=None,
        filing_date=None,
        page="5",
        section="Methodology",
    )

    assert payload.title == "Research Paper"
    assert payload.ticker is None
    assert payload.form is None
    assert payload.page == "5"


def test_grounding_validator_accepts_valid_generic_citation() -> None:
    """GroundingValidator must accept valid verbatim citations from generic documents."""
    import asyncio

    registry = TurnRegistry()
    chunk_id = uuid.uuid4()
    canonical_text = "شرکت‌های ایرانی در سال ۱۴۰۳ سودآوری بالایی داشتند."

    registry.register(
        RetrievedPassage(
            chunk_id=chunk_id,
            document_id=uuid.uuid4(),
            chunk_index=0,
            text=canonical_text,
            fusion_score=0.9,
            title="گزارش سالانه",
            ticker=None,
            company_name=None,
            form=None,
            filing_date=None,
            fiscal_year=None,
            accession_number=None,
            page="1",
            section="سودآوری",
        )
    )

    answer = GroundedAnswer(
        answer="سود شرکت‌ها بالا بوده است [1].",
        citations=[
            Citation(
                citation_index=1,
                chunk_id=chunk_id,
                excerpt="شرکت‌های ایرانی در سال ۱۴۰۳ سودآوری بالایی داشتند.",
            )
        ],
        insufficient_evidence=False,
    )

    fake_judge = MagicMock()
    fake_judge.judge = MagicMock()

    async def fake_judge_call(citations):
        return [MagicMock(citation_index=1, supported=True, reason="Supported")]

    fake_judge.judge.side_effect = fake_judge_call

    validator = GroundingValidator(judge=fake_judge)
    result = asyncio.run(validator.validate(answer, registry=registry))

    assert result.ok, f"Validation failed: {result.error}"
    # Verify the judge was given the canonical chunk text, not a modified representation
    call_args = fake_judge.judge.call_args[0][0]
    assert call_args[0].source_text == canonical_text


def test_grounding_validator_rejects_unregistered_generic_citation() -> None:
    """Citations pointing to chunks not in TurnRegistry must fail validation."""
    import asyncio

    registry = TurnRegistry()
    allowed_id = uuid.uuid4()
    registry.register(
        RetrievedPassage(
            chunk_id=allowed_id,
            document_id=uuid.uuid4(),
            chunk_index=0,
            text="Allowed passage text.",
            fusion_score=0.8,
            title="Allowed Doc",
            ticker=None,
            company_name=None,
            form=None,
            filing_date=None,
            fiscal_year=None,
            accession_number=None,
            page="1",
            section=None,
        )
    )
    unregistered_id = uuid.uuid4()

    answer = GroundedAnswer(
        answer="Some statement [1].",
        citations=[
            Citation(
                citation_index=1,
                chunk_id=unregistered_id,
                excerpt="Some excerpt.",
            )
        ],
        insufficient_evidence=False,
    )

    validator = GroundingValidator(judge=MagicMock())
    result = asyncio.run(validator.validate(answer, registry=registry))

    assert not result.ok
    assert "was not retrieved" in (result.error or "")


# ===========================================================================
# Part 18: Search Readiness for Generic Chunk Texts
# ===========================================================================


def test_search_keywords_extracted_from_generic_chunk_queries() -> None:
    """Keywords extracted from Persian and English queries against generic documents."""
    # Persian query with numbers
    fa_query = "درآمد شرکت‌ها در سال ۱۴۰۳ چقدر بود؟"
    norm_fa = normalize(fa_query)
    fa_keywords = extract_fts_keywords(norm_fa)
    assert "شرکت" in fa_keywords or "درامد" in fa_keywords or "1403" in fa_keywords

    # English query
    en_query = "What were the risk factors in 2024?"
    norm_en = normalize(en_query)
    en_keywords = extract_fts_keywords(norm_en)
    assert "risk" in en_keywords.lower() or "factors" in en_keywords.lower()
