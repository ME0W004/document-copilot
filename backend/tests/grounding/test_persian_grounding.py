import asyncio
import uuid
from datetime import date

from app.assistant.deps import TurnRegistry
from app.assistant.outputs import Citation, GroundedAnswer
from app.grounding.validator import (
    CitationGroundingCase,
    CitationGroundingDecision,
    GroundingValidator,
    prune_unreferenced_citations,
)
from app.retrieval.types import RetrievedPassage

PERSIAN_SOURCE = (
    "درآمد بخش ابری Azure در سال مالی 2024 با رشد 29 درصدی به 37.6 میلیارد دلار "
    "رسید. مدیریت شرکت این رشد را نتیجه افزایش تقاضا برای سرویس‌های ابری دانست."
)
PERSIAN_EXCERPT = (
    "درآمد بخش ابری Azure در سال مالی 2024 با رشد 29 درصدی به 37.6 میلیارد دلار رسید"
)
PERSIAN_ANSWER = (
    "درآمد بخش Azure در سال مالی 2024 با رشد 29 درصدی به 37.6 میلیارد دلار رسید [1]."
)
ENGLISH_SOURCE = (
    "Azure revenue grew 29% in fiscal 2024. Management attributed the growth to "
    "increased demand for cloud services."
)


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


def _citation(passage: RetrievedPassage, excerpt: str, index: int = 1) -> Citation:
    return Citation(citation_index=index, chunk_id=passage.chunk_id, excerpt=excerpt)


def _registry(*passages: RetrievedPassage) -> TurnRegistry:
    registry = TurnRegistry()
    registry.register_many(list(passages))
    return registry


def _validate(answer: GroundedAnswer, registry: TurnRegistry, judge):
    return asyncio.run(GroundingValidator(judge=judge).validate(answer, registry))


class RecordingSupportedJudge:
    """Supports every case and records exactly what it received."""

    def __init__(self) -> None:
        self.calls: list[CitationGroundingCase] = []

    async def judge(
        self, cases: list[CitationGroundingCase]
    ) -> list[CitationGroundingDecision]:
        self.calls.extend(cases)
        return [
            CitationGroundingDecision(
                citation_index=case.citation_index,
                supported=True,
                reason="supported",
            )
            for case in cases
        ]


class UnsupportedJudge:
    async def judge(
        self, cases: list[CitationGroundingCase]
    ) -> list[CitationGroundingDecision]:
        return [
            CitationGroundingDecision(
                citation_index=case.citation_index,
                supported=False,
                reason="unsupported",
            )
            for case in cases
        ]


class StrictVerbatimJudge:
    """Supports a citation only when the excerpt is a codepoint-exact substring."""

    async def judge(
        self, cases: list[CitationGroundingCase]
    ) -> list[CitationGroundingDecision]:
        return [
            CitationGroundingDecision(
                citation_index=case.citation_index,
                supported=case.excerpt in case.source_text,
                reason="verbatim" if case.excerpt in case.source_text else "not verbatim",
            )
            for case in cases
        ]


def test_case_a_persian_answer_persian_source_passes() -> None:
    passage = _passage(PERSIAN_SOURCE)
    answer = GroundedAnswer(
        answer=PERSIAN_ANSWER,
        citations=[_citation(passage, PERSIAN_EXCERPT)],
    )
    judge = RecordingSupportedJudge()

    result = _validate(answer, _registry(passage), judge)

    assert result.ok
    assert judge.calls[0].answer == answer.answer
    assert judge.calls[0].excerpt == PERSIAN_EXCERPT
    assert judge.calls[0].source_text == PERSIAN_SOURCE


def test_case_b_persian_answer_english_source_passes() -> None:
    passage = _passage(ENGLISH_SOURCE)
    answer = GroundedAnswer(
        answer="درآمد Azure در سال مالی 2024 نسبت به سال قبل ۲۹ درصد رشد کرد [1].",
        citations=[_citation(passage, "Azure revenue grew 29% in fiscal 2024")],
    )

    assert _validate(answer, _registry(passage), RecordingSupportedJudge()).ok


def test_case_c_english_answer_persian_source_passes() -> None:
    passage = _passage(PERSIAN_SOURCE)
    answer = GroundedAnswer(
        answer="Azure cloud revenue grew 29% to $37.6 billion in fiscal 2024 [1].",
        citations=[_citation(passage, PERSIAN_EXCERPT)],
    )

    assert _validate(answer, _registry(passage), RecordingSupportedJudge()).ok


def test_case_d_mixed_answer_bilingual_source_passes() -> None:
    passage = _passage(
        "Azure revenue grew 29% in fiscal 2024. مدیریت شرکت این رشد را نتیجه "
        "افزایش تقاضای ابری دانست."
    )
    answer = GroundedAnswer(
        answer="Azure revenue در سال مالی 2024 رشد کرد [1].",
        citations=[_citation(passage, "Azure revenue grew 29% in fiscal 2024")],
    )

    assert _validate(answer, _registry(passage), RecordingSupportedJudge()).ok


def test_case_e_persian_answer_invalid_citation_fails() -> None:
    passage = _passage(PERSIAN_SOURCE)
    answer = GroundedAnswer(
        answer=PERSIAN_ANSWER,
        citations=[
            _citation(passage, PERSIAN_EXCERPT),
            _citation(passage, "سرویس‌های ابری", index=2),
        ],
    )

    result = _validate(answer, _registry(passage), RecordingSupportedJudge())

    assert not result.ok
    assert "markers" in (result.error or "")


def test_case_f_persian_answer_unregistered_chunk_fails() -> None:
    passage = _passage(PERSIAN_SOURCE)
    answer = GroundedAnswer(
        answer=PERSIAN_ANSWER,
        citations=[_citation(_passage(PERSIAN_SOURCE), PERSIAN_EXCERPT)],
    )

    result = _validate(answer, _registry(passage), RecordingSupportedJudge())

    assert not result.ok
    assert "not retrieved" in (result.error or "")


def test_case_g_persian_answer_fabricated_excerpt_fails() -> None:
    passage = _passage(PERSIAN_SOURCE)
    answer = GroundedAnswer(
        answer=PERSIAN_ANSWER,
        citations=[_citation(passage, "این جمله در متن منبع وجود ندارد.")],
    )

    result = _validate(answer, _registry(passage), UnsupportedJudge())

    assert not result.ok
    assert "not supported" in (result.error or "")


def test_case_h_persian_insufficient_evidence_has_zero_citations() -> None:
    answer = GroundedAnswer(
        answer="مدارک کافی برای پاسخ در منابع بازیابی‌شده پیدا نشد.",
        citations=[],
        insufficient_evidence=True,
    )

    assert _validate(answer, TurnRegistry(), RecordingSupportedJudge()).ok


def test_case_h_persian_insufficient_evidence_rejects_citations() -> None:
    passage = _passage(PERSIAN_SOURCE)
    answer = GroundedAnswer(
        answer="مدارک کافی برای پاسخ در منابع بازیابی‌شده پیدا نشد.",
        citations=[_citation(passage, PERSIAN_EXCERPT)],
        insufficient_evidence=True,
    )

    assert not _validate(answer, _registry(passage), RecordingSupportedJudge()).ok


def test_case_i_persian_answer_ascii_marker_passes() -> None:
    passage = _passage(PERSIAN_SOURCE)
    answer = GroundedAnswer(
        answer="رشد سرویس‌های ابری Microsoft ادامه داشت [1].",
        citations=[_citation(passage, PERSIAN_EXCERPT)],
    )

    assert _validate(answer, _registry(passage), RecordingSupportedJudge()).ok


def test_case_j_persian_digit_marker_fails_ascii_contract() -> None:
    passage = _passage(PERSIAN_SOURCE)
    answer = GroundedAnswer(
        answer="درآمد ابری رشد کرد [۱].",
        citations=[_citation(passage, PERSIAN_EXCERPT)],
    )

    result = _validate(answer, _registry(passage), RecordingSupportedJudge())

    assert not result.ok


def test_arabic_indic_digit_marker_fails_ascii_contract() -> None:
    passage = _passage(PERSIAN_SOURCE)
    answer = GroundedAnswer(
        answer="درآمد ابری رشد کرد [١].",
        citations=[_citation(passage, PERSIAN_EXCERPT)],
    )

    result = _validate(answer, _registry(passage), RecordingSupportedJudge())

    assert not result.ok


def test_persian_digit_markers_are_not_pruned_as_referenced() -> None:
    passage = _passage(PERSIAN_SOURCE)
    answer = GroundedAnswer(
        answer="درآمد ابری رشد کرد [۱].",
        citations=[_citation(passage, PERSIAN_EXCERPT)],
    )

    pruned = prune_unreferenced_citations(answer)

    assert [citation.citation_index for citation in pruned.citations] == [1]
    assert not _validate(pruned, _registry(passage), RecordingSupportedJudge()).ok


def test_excerpt_with_special_persian_characters_reaches_judge_verbatim() -> None:
    # Source mixes Arabic yeh/kaf (ي ك), Persian yeh/kaf (ی ک), ZWNJ, Persian and
    # Arabic-Indic digits, Persian punctuation, and embedded English terms.
    source = (
        "شرکت ك در سال ۱۴۰۳ (معادل 2024) رشد يافت؛ سرویس‌های ابری و cloud revenue "
        "هر دو به ۱۲٣ میلیارد رسیدند، و تقاضا در نیمه دوم سال بیشتر شد؟"
    )
    excerpt = "شرکت ك در سال ۱۴۰۳ (معادل 2024) رشد يافت؛ سرویس‌های ابری"
    assert excerpt in source
    passage = _passage(source)
    answer = GroundedAnswer(
        answer="رشد درآمد ثبت شد [1].",
        citations=[_citation(passage, excerpt)],
    )
    judge = RecordingSupportedJudge()

    result = _validate(answer, _registry(passage), judge)

    assert result.ok
    assert judge.calls[0].excerpt == excerpt
    assert judge.calls[0].source_text == source


def test_validator_does_not_normalize_excerpt_against_canonical_text() -> None:
    # The canonical chunk uses Arabic yeh/kaf; the excerpt spells the same words
    # with Persian yeh/kaf. Citation validation must not fold that difference —
    # document_chunks.text stays the verbatim canon.
    passage = _passage("شرکت ك رشد يافت")
    answer = GroundedAnswer(
        answer="رشد ثبت شد [1].",
        citations=[_citation(passage, "شرکت ک رشد یافت")],
    )

    result = _validate(answer, _registry(passage), StrictVerbatimJudge())

    assert not result.ok


def test_strict_verbatim_persian_excerpt_passes() -> None:
    passage = _passage("شرکت ك رشد يافت")
    answer = GroundedAnswer(
        answer="رشد ثبت شد [1].",
        citations=[_citation(passage, "شرکت ك رشد يافت")],
    )

    assert _validate(answer, _registry(passage), StrictVerbatimJudge()).ok


def test_prune_unreferenced_citations_with_persian_answer() -> None:
    first = _passage(PERSIAN_SOURCE)
    second = _passage(ENGLISH_SOURCE)
    answer = GroundedAnswer(
        answer="درآمد ابری رشد کرد [1].",
        citations=[_citation(first, PERSIAN_EXCERPT), _citation(second, "x", index=2)],
    )

    pruned = prune_unreferenced_citations(answer)

    assert [citation.citation_index for citation in pruned.citations] == [1]
