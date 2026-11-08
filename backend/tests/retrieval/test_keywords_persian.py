"""Persian-aware keyword extraction tests (Sprint 2)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.retrieval.keywords import (
    _deterministic_fallback,
    extract_fts_keywords,
    tokenize,
)

PERSIAN_QUERY = "مهم‌ترین ریسک‌های درآمد خدمات ابری چیست؟"
MIXED_QUERY = "ریسک‌های AWS در 10-K سال 2024 چیست؟"


@patch("app.retrieval.keywords._client")
def test_persian_tokens_survive_extraction(mock_client: MagicMock) -> None:
    result = extract_fts_keywords(PERSIAN_QUERY)

    assert result
    for token in ("ریسک‌های", "درآمد", "خدمات", "ابری"):
        assert token in result
    mock_client.return_value.chat.completions.parse.assert_not_called()


@patch("app.retrieval.keywords._client")
def test_short_persian_query_takes_deterministic_path(mock_client: MagicMock) -> None:
    # "ریسک ابری چیست؟" is within the fast-path token budget, but the fast
    # path would pass "چیست" through and AND-match nothing. The Persian path
    # must drop it instead.
    result = extract_fts_keywords("ریسک ابری چیست؟")

    assert "چیست" not in result
    assert "ریسک" in result
    assert "ابری" in result
    mock_client.return_value.chat.completions.parse.assert_not_called()


@patch("app.retrieval.keywords._client")
def test_persian_stopwords_and_question_words_removed(mock_client: MagicMock) -> None:
    result = extract_fts_keywords("چه عواملی بر حاشیه سود ناخالص تأثیر گذاشت؟")

    words = result.split()
    for banned in ("چه", "بر", "چیست", "چگونه", "در", "را", "با"):
        assert banned not in words
    for required in ("عواملی", "حاشیه", "سود", "ناخالص"):
        assert required in words
    mock_client.return_value.chat.completions.parse.assert_not_called()


@patch("app.retrieval.keywords._client")
def test_mixed_persian_english_tokens_all_survive(mock_client: MagicMock) -> None:
    result = extract_fts_keywords(MIXED_QUERY)

    for token in ("ریسک‌های", "AWS", "10-K", "سال", "2024"):
        assert token in result
    assert "چیست" not in result.split()
    assert "در" not in result.split()
    mock_client.return_value.chat.completions.parse.assert_not_called()


@patch("app.retrieval.keywords._client")
def test_result_respects_maximum_keyword_count(mock_client: MagicMock) -> None:
    # Seven content words; the extractor must cap at the configured maximum.
    result = extract_fts_keywords("خلاصه بحث مدیریت مورد چشم‌انداز بلندمدت را بگو")

    assert len(result.split()) <= 5
    mock_client.return_value.chat.completions.parse.assert_not_called()


def test_arabic_variants_produce_normalized_keywords() -> None:
    raw = "شركت در سال ۱۴٠٣ چه رشدی داشت؟"
    persian_spelling = "شرکت در سال 1403 چه رشدی داشت؟"

    result = extract_fts_keywords(raw)

    assert result == extract_fts_keywords(persian_spelling)
    assert "شرکت" in result
    assert "1403" in result


def test_all_stopword_query_returns_original() -> None:
    result = extract_fts_keywords("چیست؟")

    assert result == "چیست؟"


def test_deterministic_fallback_keeps_persian_tokens() -> None:
    # The English LLM-refinement fallback must not lose Persian tokens.
    result = _deterministic_fallback("ریسک‌های AWS چیست", filters=None)

    assert "ریسک‌های" in result
    assert "AWS" in result
    assert "چیست" not in result.split()


def test_tokenize_separates_on_persian_punctuation() -> None:
    tokens = tokenize("شرکت،بازار؛سود؟")

    assert tokens == ["شرکت", "بازار", "سود"]


def test_tokenize_keeps_zwnj_hyphen_and_slash_tokens() -> None:
    tokens = tokenize("می‌روم ریسک‌های 10-K و FY2024/25")

    assert "می‌روم" in tokens
    assert "ریسک‌های" in tokens
    assert "10-K" in tokens
    assert "FY2024/25" in tokens
