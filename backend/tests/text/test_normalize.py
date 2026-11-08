"""Behavior tests for the Persian normalizer: input → expected output."""

from __future__ import annotations

import pytest

from app.text.normalize import (
    normalize,
    normalize_whitespace,
    strip_diacritics,
)

# Arabic keyboard/OCR variants, spelled with explicit codepoints so the
# fixtures are unambiguous: ي=U+064A, ى=U+0649, ك=U+0643. ZWNJ is invisible,
# so it always appears as the ZWNJ constant.
YEH_ARABIC = "\u064a"
ALEF_MAKSURA = "\u0649"
KAF_ARABIC = "\u0643"
ZWNJ = "\u200c"


class TestArabicLetterVariants:
    def test_arabic_yeh_and_kaf_fold_to_persian(self) -> None:
        # "يک شركت" → "یک شرکت" (kaf is the third letter of شركت)
        assert normalize(f"{YEH_ARABIC}ک شر{KAF_ARABIC}ت") == "یک شرکت"

    def test_alef_maksura_folds_to_persian_yeh(self) -> None:
        # "على" (Arabic spelling) → "علی"
        assert normalize(f"عل{ALEF_MAKSURA}") == "علی"

    def test_presentation_forms_decompose(self) -> None:
        # U+FEFB lam-alef isolated form (typical of PDF/OCR text) → "لا"
        assert normalize("\ufefb") == "لا"

    def test_tatweel_is_removed(self) -> None:
        # "کتــاب" with two U+0640 kashidas → "کتاب"
        assert normalize("کتــــاب") == "کتاب"


class TestDigits:
    def test_persian_digits_fold_to_ascii(self) -> None:
        assert normalize("۱۴۰۳") == "1403"

    def test_arabic_indic_digits_fold_to_ascii(self) -> None:
        assert normalize("١٤٠٣") == "1403"

    def test_ascii_digits_unchanged(self) -> None:
        assert normalize("1403") == "1403"

    def test_digits_inside_mixed_text(self) -> None:
        assert normalize("FY۱۴۰۳ و سال ١٤٠٤") == "FY1403 و سال 1404"


class TestDiacritics:
    def test_attached_diacritics_are_removed(self) -> None:
        # مُحَمَّد → محمد (damma, fatha, shadda)
        assert normalize("مُحَمَّد") == "محمد"

    def test_kasra_and_fatha_removed_along_with_letter_folding(self) -> None:
        # "كِتَاب" → "کتاب" (ك→ک, kasra/fatha stripped)
        assert normalize("كِتَاب") == "کتاب"

    def test_standalone_diacritics_are_removed(self) -> None:
        assert normalize("َ ِ ُ ّ ْ") == ""

    def test_punctuation_is_not_removed(self) -> None:
        assert strip_diacritics("مَ؟") == "م؟"


class TestZwnj:
    def test_valid_zwnj_is_preserved(self) -> None:
        assert normalize(f"می{ZWNJ}روم") == f"می{ZWNJ}روم"
        assert normalize(f"هم{ZWNJ}کاران") == f"هم{ZWNJ}کاران"

    def test_repeated_zwnj_collapses(self) -> None:
        assert normalize(f"می{ZWNJ}{ZWNJ}روم") == f"می{ZWNJ}روم"

    def test_zwnj_next_to_whitespace_is_dropped(self) -> None:
        assert normalize(f"می{ZWNJ} رود") == "می رود"
        assert normalize("می  رود") == "می رود"
        assert normalize(f" {ZWNJ}می") == "می"

    def test_zwnj_next_to_non_arabic_is_dropped(self) -> None:
        assert normalize(f"abc{ZWNJ}def") == "abcdef"
        assert normalize(f"5{ZWNJ}۰") == "50"

    def test_stray_zwnj_between_letters_is_preserved(self) -> None:
        # "می‌ر‌وم" — a stray ZWNJ cannot be told from a legitimate one
        # without morphology; Sprint 1 policy is to preserve it.
        assert normalize(f"می{ZWNJ}ر{ZWNJ}وم") == f"می{ZWNJ}ر{ZWNJ}وم"


class TestWhitespace:
    def test_repeated_spaces_and_edge_whitespace_collapse(self) -> None:
        assert normalize("  متن   اول\n\nمتن دوم  ") == "متن اول\n\nمتن دوم"

    def test_tabs_become_single_space(self) -> None:
        assert normalize("a\tb") == "a b"

    def test_paragraph_boundaries_are_preserved(self) -> None:
        assert normalize("خط اول\nخط دوم") == "خط اول\nخط دوم"

    def test_newline_runs_capped_at_paragraph_break(self) -> None:
        assert normalize("a\n\n\n\n\nb") == "a\n\nb"

    def test_carriage_returns_become_newlines(self) -> None:
        assert normalize("cr\r\nlf") == "cr\nlf"
        assert normalize_whitespace("a\rb") == "a\nb"


class TestMixedPersianEnglish:
    def test_english_terms_survive_untouched(self) -> None:
        assert normalize("نرخ رشد Revenue در FY2024") == (
            "نرخ رشد Revenue در FY2024"
        )
        assert normalize("OpenAI API در سیستم") == "OpenAI API در سیستم"
        assert normalize("10-K شرکت") == "10-K شرکت"
        assert normalize("Python و PostgreSQL") == "Python و PostgreSQL"

    def test_variants_and_digits_inside_mixed_text(self) -> None:
        assert normalize(f"شر{KAF_ARABIC}ت Apple که در FY۱۴۰۳") == (
            "شرکت Apple که در FY1403"
        )


class TestTrivialInputs:
    def test_empty_and_whitespace_only(self) -> None:
        assert normalize("") == ""
        assert normalize(" ") == ""
        assert normalize("\n") == ""
        assert normalize("\t \n ") == ""

    def test_none_is_rejected_not_silently_converted(self) -> None:
        with pytest.raises(TypeError):
            normalize(None)  # type: ignore[arg-type]


class TestPreservation:
    def test_meaningful_content_survives(self) -> None:
        result = normalize("Revenue growth\n\nدر شرکت 10-K")
        assert "Revenue" in result
        assert "10-K" in result
        assert "\n\n" in result
        assert "شرکت" in result

    def test_plain_persian_text_is_unchanged(self) -> None:
        assert normalize("پارامترها در بازار سرمایه") == (
            "پارامترها در بازار سرمایه"
        )

    def test_input_string_is_not_mutated(self) -> None:
        source = "  متن   اول\n\nمتن دوم  "
        normalize(source)
        assert source == "  متن   اول\n\nمتن دوم  "


_IDEMPOTENCE_FIXTURES = [
    f"{YEH_ARABIC}ک شر{KAF_ARABIC}ت",
    f"عل{ALEF_MAKSURA}",
    "\ufefb",
    "کتــــاب",
    "۱۴۰۳",
    "١٤٠٣",
    "مُحَمَّد",
    f"می{ZWNJ}روم",
    f"می{ZWNJ}{ZWNJ}روم",
    f"می{ZWNJ} رود",
    f"می{ZWNJ}ر{ZWNJ}وم",
    "  متن   اول\n\nمتن دوم  ",
    "نرخ رشد Revenue در FY2024",
    "10-K شرکت",
    "",
    " ",
    "\n",
]


class TestIdempotence:
    @pytest.mark.parametrize("text", _IDEMPOTENCE_FIXTURES)
    def test_normalize_is_idempotent(self, text: str) -> None:
        once = normalize(text)
        assert normalize(once) == once
