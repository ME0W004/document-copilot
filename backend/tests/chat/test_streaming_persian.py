import json
import uuid
from datetime import date

import pytest

from app.assistant.deps import TurnRegistry
from app.assistant.outputs import Citation, GroundedAnswer
from app.chat.streaming import stream_grounded_answer
from app.retrieval.types import RetrievedPassage

PERSIAN_ANSWER = "درآمد سرویس‌های ابری Azure در سال مالی 2024 رشد کرد [1]."
PERSIAN_EXCERPT = "درآمد بخش ابری Azure در سال مالی 2024 با رشد 29 درصدی رسید."


def _answer_and_registry() -> tuple[GroundedAnswer, TurnRegistry]:
    chunk_id = uuid.uuid4()
    passage = RetrievedPassage(
        chunk_id=chunk_id,
        document_id=uuid.uuid4(),
        chunk_index=0,
        text=PERSIAN_EXCERPT,
        page="15",
        section="MD&A",
        fusion_score=0.6,
        ticker="MSFT",
        company_name="Microsoft Corporation",
        form="10-K",
        filing_date=date(2024, 7, 30),
        fiscal_year=2024,
        accession_number="0000789019-24-000012",
    )
    registry = TurnRegistry()
    registry.register(passage)
    answer = GroundedAnswer(
        answer=PERSIAN_ANSWER,
        citations=[
            Citation(citation_index=1, chunk_id=chunk_id, excerpt=PERSIAN_EXCERPT)
        ],
    )
    return answer, registry


@pytest.mark.anyio
async def test_persian_answer_streams_and_roundtrips_exactly() -> None:
    answer, registry = _answer_and_registry()

    events = [
        event
        async for event in stream_grounded_answer(
            answer,
            registry,
            message_id=str(uuid.uuid4()),
        )
    ]

    payloads = [json.loads(event.removeprefix("data: ")) for event in events]
    streamed_text = "".join(
        payload["delta"] for payload in payloads if payload.get("type") == "text-delta"
    )

    # json.dumps escapes Persian as \uXXXX on the wire; decoding must restore
    # the exact text, including ZWNJ and ASCII citation markers.
    assert streamed_text.strip() == PERSIAN_ANSWER
    assert "\u200c" in streamed_text
    assert "[1]" in streamed_text

    citation_payload = next(
        payload for payload in payloads if payload.get("type") == "data-citation"
    )
    assert citation_payload["data"]["excerpt"] == PERSIAN_EXCERPT
