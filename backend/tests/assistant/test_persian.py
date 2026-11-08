import json
import uuid
from datetime import date

from app.assistant.agent import INSTRUCTIONS
from app.assistant.outputs import GroundedAnswer
from app.retrieval.types import RetrievedPassage, format_passages_for_agent


def _passage(text: str) -> RetrievedPassage:
    chunk_id = uuid.uuid4()
    return RetrievedPassage(
        chunk_id=chunk_id,
        document_id=uuid.uuid4(),
        chunk_index=0,
        text=text,
        page="10",
        section="MD&A",
        fusion_score=0.8,
        ticker="MSFT",
        company_name="Microsoft Corporation",
        form="10-K",
        filing_date=date(2024, 7, 30),
        fiscal_year=2024,
        accession_number="0000789019-24-000012",
    )


def test_instructions_map_question_language_to_answer_language() -> None:
    assert "same language as the user's question" in INSTRUCTIONS
    assert "Persian question gets a Persian answer" in INSTRUCTIONS
    assert "English question gets an English answer" in INSTRUCTIONS
    assert "dominant language of the question" in INSTRUCTIONS


def test_instructions_keep_source_and_answer_language_independent() -> None:
    assert "independent of the source language" in INSTRUCTIONS
    assert "may cite English passages" in INSTRUCTIONS
    assert "may cite Persian passages" in INSTRUCTIONS


def test_instructions_preserve_technical_terms_policy() -> None:
    assert "technical financial terms" in INSTRUCTIONS
    assert "transliterating" in INSTRUCTIONS
    assert "never translate an excerpt" in INSTRUCTIONS


def test_instructions_require_ascii_citation_markers() -> None:
    assert "ASCII digits" in INSTRUCTIONS
    assert "[۱]" in INSTRUCTIONS


def test_instructions_keep_existing_safety_rules() -> None:
    for fragment in (
        "Never invent facts",
        "**verbatim excerpt**",
        "Do not fabricate citations",
        "**No stock picks**",
        "`insufficient_evidence` to true",
        "return an **empty** citations list",
    ):
        assert fragment in INSTRUCTIONS


def test_answer_field_description_is_language_neutral() -> None:
    schema = GroundedAnswer.model_json_schema()
    description = schema["properties"]["answer"]["description"]

    assert "Plain-English" not in json.dumps(schema)
    assert "user's language" in description
    assert "ASCII [n] citation markers" in description


def test_grounded_answer_schema_shape_unchanged() -> None:
    schema = GroundedAnswer.model_json_schema()

    assert set(schema["properties"]) == {
        "answer",
        "citations",
        "insufficient_evidence",
    }
    assert schema["required"] == ["answer"]

    citation_schema = schema["$defs"]["Citation"]
    assert set(citation_schema["properties"]) == {
        "citation_index",
        "chunk_id",
        "excerpt",
    }
    assert set(citation_schema["required"]) == {"citation_index", "chunk_id", "excerpt"}


def test_format_passages_for_agent_preserves_persian_text() -> None:
    text = "درآمد سرویس‌های ابری Azure در سال مالی 2024 رشد کرد."
    passage = _passage(text)

    output = format_passages_for_agent([passage])

    assert str(passage.chunk_id) in output
    assert "MSFT" in output
    assert text in output
    assert "\u200c" in output


def test_format_passages_for_agent_truncates_long_persian_text() -> None:
    text = "پاراگراف فارسی درباره درآمد سالانه " * 60
    passage = _passage(text)

    output = format_passages_for_agent([passage])

    assert text.strip()[:800] in output
    assert "..." in output
