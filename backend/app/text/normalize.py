"""Deterministic Persian text normalization.

Sprint 1 of the Persian Language Core: a pure-stdlib normalization layer that
later sprints use to derive normalized/search representations of document and
query text.

Canonical data contract: `document_chunks.text` is the original canonical text
used for citations, excerpts, and grounding. It is never rewritten. The output
of `normalize()` is derived text used only for retrieval/search.

The pipeline runs in a fixed order and every stage is idempotent, so
`normalize(normalize(text)) == normalize(text)`:

1. Arabic presentation forms → standard letters (targeted NFKC).
2. Arabic letter variants → Persian letters (ي ى → ی, ك → ک).
3. Persian and Arabic-Indic digits → ASCII digits.
4. Arabic diacritics (tashkeel, Quranic combining marks) and tatweel removed.
5. Bidi control characters removed.
6. ZWNJ cleanup (collapse repeats, drop positions where nothing can join).
7. Whitespace normalization (tabs/narrow spaces → space, paragraphs kept).
"""

from __future__ import annotations

import re
import unicodedata

_ZWNJ = "\u200c"

# Arabic presentation forms (U+FB50–U+FDFF, U+FE70–U+FEFF) leak into Persian
# text from PDFs and OCR. NFKC decomposes them to standard letters. Applying
# it only inside these blocks never touches Latin text or standard Persian.
_PRESENTATION_FORM_RANGES = (
    (0xFB50, 0xFDFF),
    (0xFE70, 0xFEFF),
)

# Arabic-script letters that are keyboard/OCR variants of a Persian letter.
# In Persian orthography the Arabic codepoint is always a stand-in for the
# Persian one, so folding cannot change Persian word identity. Hamza carriers
# (أ إ ؤ ئ), teh marbuta (ة), and heh-with-yeh (ۀ) are deliberately NOT
# folded: they distinguish spellings in Arabic loanwords and ezafe forms.
_ARABIC_TO_PERSIAN = {
    "\u064a": "\u06cc",  # ARABIC LETTER YEH → FARSI YEH
    "\u0649": "\u06cc",  # ALEF MAKSURA → FARSI YEH (final-yeh variant)
    "\u0643": "\u06a9",  # ARABIC LETTER KAF → KEHEH
}

# Extended Arabic-Indic (Persian, U+06F0–U+06F9) and Arabic-Indic
# (U+0660–U+0669) digits fold to ASCII so ۱۴۰۳, ١٤٠٣, and 1403 all match.
_DIGIT_FOLDS: dict[int, str] = {
    **{0x06F0 + d: str(d) for d in range(10)},
    **{0x0660 + d: str(d) for d in range(10)},
}

# Combining marks removed for matching. Every range below is Unicode
# category Mn (or the pure typographic tatweel). Letters, hamza carriers,
# and Arabic punctuation (، ؛ ؟) are never touched.
_DIACRITIC_RANGES = (
    (0x0610, 0x061A),  # honorific / Quranic annotation signs
    (0x0640, 0x0640),  # tatweel (kashida) — typographic stretching, no meaning
    (0x064B, 0x065F),  # tashkeel: fathatan..small Rakhna (fatha, damma,
    #                    kasra, shadda, sukun, hamza-above/below marks)
    (0x0670, 0x0670),  # superscript alef
    (0x06D6, 0x06DC),  # Quranic small high marks
    (0x06DF, 0x06E8),  # Quranic small letters and marks
    (0x06EA, 0x06ED),  # Quranic empty-centre signs
)

# Directional formatting controls (LRM/RLM, embedding/pop, isolates) shape
# rendering only, never word identity; they are noise for matching. ZWJ is
# deliberately NOT removed: it is meaningful in emoji sequences and other
# scripts that may appear in mixed text.
_BIDI_CONTROLS = (
    "\u200e\u200f"  # LRM, RLM
    "\u202a\u202b\u202c\u202d\u202e"  # LRE, RLE, PDF, LRO, RLO
    "\u2066\u2067\u2068\u2069"  # LRI, RLI, FSI, PDI
)
_BIDI_CONTROL_TABLE = {ord(ch): None for ch in _BIDI_CONTROLS}

# Ranges that can contain Arabic-script letters after stage 1. Used to decide
# whether a ZWNJ sits between two letters (where it prevents joining and is
# therefore meaningful). Category Lo excludes Arabic punctuation (، ؛ ؟)
# and invisible number signs that share these blocks.
_ARABIC_LETTER_RANGES = (
    (0x0600, 0x06FF),
    (0x0750, 0x077F),
    (0x08A0, 0x08FF),
    (0xFB50, 0xFDFF),
    (0xFE70, 0xFEFF),
)


def _in_ranges(code: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(lo <= code <= hi for lo, hi in ranges)


def _is_arabic_letter(ch: str | None) -> bool:
    if ch is None:
        return False
    if not _in_ranges(ord(ch), _ARABIC_LETTER_RANGES):
        return False
    return unicodedata.category(ch) == "Lo"


def normalize_codepoints(text: str) -> str:
    """Fold Arabic presentation forms and Arabic letter variants to Persian."""
    out: list[str] = []
    for ch in text:
        if _in_ranges(ord(ch), _PRESENTATION_FORM_RANGES):
            ch = unicodedata.normalize("NFKC", ch)
        out.append(_ARABIC_TO_PERSIAN.get(ch, ch))
    return "".join(out)


def normalize_digits(text: str) -> str:
    """Fold Persian (۰-۹) and Arabic-Indic (٠-٩) digits to ASCII."""
    return text.translate(_DIGIT_FOLDS)


def strip_diacritics(text: str) -> str:
    """Remove Arabic/Persian combining marks and tatweel; keep all letters."""
    return "".join(
        ch for ch in text if not _in_ranges(ord(ch), _DIACRITIC_RANGES)
    )


def normalize_zwnj(text: str) -> str:
    """Collapse malformed ZWNJ while preserving meaningful ones.

    Policy (documented in docs/persian-text-normalization.md):

    - Repeated ZWNJ runs collapse to a single ZWNJ.
    - ZWNJ is kept only between two Arabic-script letters, where it prevents
      joining and is linguistically meaningful (می‌روم, هم‌کاران).
    - ZWNJ adjacent to whitespace, punctuation, digits, Latin text, or a
      string boundary is redundant and dropped; the surrounding whitespace
      normalization then decides separation (می‌ رود → می رود).
    - ZWNJ is never rewritten to a space and never deleted wholesale.

    A single stray ZWNJ inside a word (می‌ر‌وم) cannot be distinguished from
    a legitimate one without morphological analysis, so it is preserved.
    """
    text = re.sub(f"{_ZWNJ}{{2,}}", _ZWNJ, text)
    chars = list(text)
    kept: list[str] = []
    for i, ch in enumerate(chars):
        if ch != _ZWNJ:
            kept.append(ch)
            continue
        prev = chars[i - 1] if i > 0 else None
        nxt = chars[i + 1] if i + 1 < len(chars) else None
        if _is_arabic_letter(prev) and _is_arabic_letter(nxt):
            kept.append(ch)
    return "".join(kept)


def normalize_whitespace(text: str) -> str:
    """Collapse whitespace runs while keeping paragraph boundaries.

    Tabs and every Unicode whitespace except newline become a single space.
    Newline runs are capped at two (one blank line) so paragraph breaks
    survive; single line breaks are preserved as-is.
    """
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[\u2028\u2029]", "\n", text)
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize(text: str) -> str:
    """Return the normalized/search form of `text`.

    Deterministic and idempotent. The input string is never mutated (strings
    are immutable in Python); callers own the original and must keep it as
    the canonical citation text.
    """
    text = normalize_codepoints(text)
    text = normalize_digits(text)
    text = strip_diacritics(text)
    text = text.translate(_BIDI_CONTROL_TABLE)
    text = normalize_zwnj(text)
    return normalize_whitespace(text)
