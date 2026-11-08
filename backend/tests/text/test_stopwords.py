"""Behavior tests for the Persian stopword set."""

from __future__ import annotations

from app.text.stopwords import PERSIAN_STOPWORDS, is_stopword

CORE_FUNCTION_WORDS = [
    "و", "در", "به", "از", "که", "را", "با", "برای", "این", "آن",
    "یک", "تا", "بر", "یا", "اما", "اگر", "هم", "نیز",
]


def test_core_function_words_are_stopwords() -> None:
    for token in CORE_FUNCTION_WORDS:
        assert token in PERSIAN_STOPWORDS


def test_content_words_are_not_stopwords() -> None:
    for token in ["شرکت", "درآمد", "بازار", "Revenue", "1403"]:
        assert token not in PERSIAN_STOPWORDS
        assert not is_stopword(token)


def test_is_stopword_normalizes_its_input() -> None:
    # "يک" with Arabic yeh (U+064A), "اَز" with fatha, " در " with spaces.
    assert is_stopword("\u064a\u06a9")
    assert is_stopword("اَز")
    assert is_stopword(" در ")
