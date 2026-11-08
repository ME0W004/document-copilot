import asyncio
import re
import uuid

import pytest

from app.assistant.agent import run_document_agent
from app.assistant.deps import DocumentAgentDeps, TurnRegistry
from app.grounding.validator import GroundingValidator
from app.retrieval.retriever import DocumentRetriever

_ARABIC_SCRIPT_RE = re.compile(r"[\u0600-\u06FF]")


def _deps() -> DocumentAgentDeps:
    return DocumentAgentDeps(
        retriever=DocumentRetriever(),
        registry=TurnRegistry(),
        thread_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
    )


@pytest.mark.integration
def test_persian_question_gets_persian_grounded_answer() -> None:
    deps = _deps()

    answer = run_document_agent(
        "درآمد بخش Azure مایکروسافت در سال مالی 2024 چگونه تغییر کرد؟",
        deps,
    )
    validation = asyncio.run(GroundingValidator().validate(answer, deps.registry))

    assert validation.ok
    assert _ARABIC_SCRIPT_RE.search(answer.answer)
    if not answer.insufficient_evidence:
        assert answer.citations


@pytest.mark.integration
def test_english_question_gets_english_answer() -> None:
    deps = _deps()

    answer = run_document_agent(
        "How did Microsoft describe Azure revenue growth in fiscal 2024?",
        deps,
    )
    validation = asyncio.run(GroundingValidator().validate(answer, deps.registry))

    assert validation.ok
    assert not _ARABIC_SCRIPT_RE.search(answer.answer)


@pytest.mark.integration
def test_mixed_question_gets_primarily_persian_answer() -> None:
    deps = _deps()

    answer = run_document_agent("ریسک‌های Microsoft در سال 2024 چیست؟", deps)
    validation = asyncio.run(GroundingValidator().validate(answer, deps.registry))

    assert validation.ok
    assert _ARABIC_SCRIPT_RE.search(answer.answer)
    if not answer.insufficient_evidence:
        assert answer.citations


@pytest.mark.integration
def test_persian_underspecified_question_refuses_with_zero_citations() -> None:
    deps = _deps()

    answer = run_document_agent("بهترین سهام برای خرید در حال حاضر چیست؟", deps)
    validation = asyncio.run(GroundingValidator().validate(answer, deps.registry))

    assert validation.ok
    assert answer.insufficient_evidence or not answer.citations
