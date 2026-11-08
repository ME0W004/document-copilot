"""Explicit Persian stopword set for lexical retrieval.

Deliberately minimal: standalone function words only, no suffix folding
(ها/های/تر/ترین). Entries are stored in normalized spelling (Persian ی/ک);
`is_stopword` normalizes its input, so callers may pass raw tokens such as
"يک".

Sprint 2 additions (retrieval evidence): question words and the colloquial
copula "هست". Filings never contain them, and the FTS query uses
plainto_tsquery AND-semantics — a single ANDed question word would zero out
the lexical leg.

No LLM dependency; the set is fully deterministic.
"""

from app.text.normalize import normalize

PERSIAN_STOPWORDS: frozenset[str] = frozenset(
    {
        # conjunctions / prepositions / particles
        "و", "در", "به", "از", "که", "را", "با", "برای", "تا", "بر",
        "روی", "یا", "اما", "اگر", "هم", "نیز", "هر", "همه", "چون", "پس",
        # demonstratives / articles
        "این", "آن", "یک",
        # copulas and auxiliaries
        "است", "بود", "شد", "شده", "باشد", "هستند", "بودند", "شود",
        # question words (Sprint 2)
        "چه", "چیست", "چگونه", "چرا", "کجا", "چند", "کدام", "چقدر", "چطور",
        # copulas and auxiliaries, continued (Sprint 2)
        "هست", "بوده",
        # pronouns
        "من", "ما", "تو", "شما", "او", "وی",
    }
)


def is_stopword(token: str) -> bool:
    """Return True if `token` is a Persian stopword after normalization."""
    return normalize(token) in PERSIAN_STOPWORDS
