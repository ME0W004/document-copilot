"""Deterministic Persian/English/mixed retrieval golden set.

Sprint 2 retrieval-evaluation fixture. Each entry pairs a query with the
contract the deterministic extraction must satisfy:

- ``must_include``: tokens that must appear in the extracted keywords.
- ``must_exclude``: tokens (stopwords, question words, filler) that must not.
- ``doc_text``: a controlled fixture document written with *unnormalized*
  spellings (Arabic yeh/kaf variants, Persian/Arabic-Indic digits,
  diacritics). When present, every extracted keyword must appear in
  ``tokenize(normalize(doc_text))`` — i.e. the normalized query keywords are
  a subset of the normalized document representation, which is exactly the
  condition under which the AND-semantics plainto_tsquery leg can match.

No expected *answers* are asserted anywhere (no corpus evidence is invented
here); ``doc_text`` documents exist only to exercise the normalization
equivalence at the lexical layer. English entries with at most 5 tokens take
the fast path (returned verbatim; the 'english' FTS config strips their
question words at query time), so they assert only ``must_include``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GoldenQuery:
    query: str
    language: str  # "persian" | "english" | "mixed"
    must_include: tuple[str, ...] = ()
    must_exclude: tuple[str, ...] = ()
    doc_text: str | None = None


PERSIAN_QUERIES: tuple[GoldenQuery, ...] = (
    GoldenQuery(
        query="مهم‌ترین ریسک‌های درآمد خدمات ابری چیست؟",
        language="persian",
        must_include=("ریسک‌های", "درآمد", "ابری"),
        must_exclude=("چیست",),
        doc_text="مدیریت شركت مهم‌ترین ریسك‌های درآمد خدمات ابری را بررسي كرد.",
    ),
    GoldenQuery(
        query="شرکت در سال 1403 چه رشدی داشت؟",
        language="persian",
        must_include=("شرکت", "سال", "1403", "رشدی"),
        must_exclude=("چه", "در"),
        doc_text="شركت اپل در سال ۱۴٠۳ رشدی بزرگ داشت.",
    ),
    GoldenQuery(
        query="درآمد خدمات ابری مایکروسافت چگونه تغییر کرد؟",
        language="persian",
        must_include=("درآمد", "خدمات", "ابری", "مایکروسافت", "تغییر"),
        must_exclude=("چگونه",),
        doc_text="شركت مایكروسافت درآمد خدمات ابری خود را در گزارش سالانه تغییر داد.",
    ),
    GoldenQuery(
        query="وضعیت بازار سرمایه در گزارش 10-K چگونه توصیف شده؟",
        language="persian",
        must_include=("وضعیت", "بازار", "سرمایه", "گزارش", "10-K"),
        must_exclude=("چگونه", "شده"),
        doc_text="در بخش ریسك‌های گزارش ۱۰-K وضعیت بازار سرمایه توصیف شده است.",
    ),
    GoldenQuery(
        query="سود هر سهم شرکت اپل چقدر بود؟",
        language="persian",
        must_include=("سود", "سهم", "شرکت", "اپل"),
        must_exclude=("چقدر", "بود", "هر"),
        doc_text="سود هر سهم شركت اپل در سال ۱۴۰۳ رشد كرد.",
    ),
    GoldenQuery(
        query="ریسک‌های زنجیره تأمین چیست؟",
        language="persian",
        must_include=("ریسک‌های", "زنجیره", "تأمین"),
        must_exclude=("چیست",),
        doc_text="شركت ریسك‌های زنجيره تأمین نیمه‌رسانا را گزارش كرد.",
    ),
    GoldenQuery(
        query="چه عواملی بر حاشیه سود ناخالص تأثیر گذاشت؟",
        language="persian",
        must_include=("عواملی", "حاشیه", "سود", "ناخالص", "تأثیر"),
        must_exclude=("چه", "بر"),
        doc_text="عواملی كه بر حاشيه سود ناخالص شركت تأثیر گذاشتند.",
    ),
    GoldenQuery(
        query="مهم‌ترین مشتریان شرکت چیست؟",
        language="persian",
        must_include=("مهم‌ترین", "مشتریان", "شرکت"),
        must_exclude=("چیست",),
        doc_text="تمركز مشتریان شركت و مهم‌ترین مشتریان آن در گزارش آمده است.",
    ),
    GoldenQuery(
        query="درباره رقابت در بازار نیمه‌رسانا توضیح بده",
        language="persian",
        must_include=("رقابت", "بازار", "نیمه‌رسانا"),
        must_exclude=("در",),
    ),
    GoldenQuery(
        query="درآمد کل شرکت در سه‌ماهه چهارم چقدر بود؟",
        language="persian",
        must_include=("درآمد", "کل", "سه‌ماهه", "چهارم"),
        must_exclude=("چقدر", "بود", "در"),
        doc_text="درآمد كل شركت در سه‌ماهه چهارم سال مالي رشد كرد.",
    ),
    GoldenQuery(
        query="در سال ۱۴۰۳ کدام بخش‌ها بیشترین رشد را داشتند؟",
        language="persian",
        must_include=("بخش‌ها", "بیشترین", "رشد", "1403"),
        must_exclude=("کدام", "را", "در"),
        doc_text="در سال ۱۴۰۳ بخش‌ها بیشترین رشد را داشتند.",
    ),
    GoldenQuery(
        query="ریسک‌های نظارتی برای شرکت چیست؟",
        language="persian",
        must_include=("ریسک‌های", "نظارتی", "شرکت"),
        must_exclude=("چیست", "برای"),
        doc_text="شركت ریسك‌هاي نظارتی فناوری را برشمرد.",
    ),
    GoldenQuery(
        query="هزینه‌های تحقیق و توسعه چگونه گزارش می‌شود؟",
        language="persian",
        must_include=("هزینه‌های", "تحقیق", "توسعه"),
        must_exclude=("چگونه", "و"),
    ),
    GoldenQuery(
        query="چشم‌انداز شرکت برای سال آینده چیست؟",
        language="persian",
        must_include=("چشم‌انداز", "آینده"),
        must_exclude=("چیست", "برای"),
        doc_text="چشم‌انداز شركت برای سال آینده مثبت است.",
    ),
    GoldenQuery(
        query="توزیع درآمد بر اساس محصول چگونه است؟",
        language="persian",
        must_include=("توزیع", "درآمد", "محصول"),
        must_exclude=("چگونه", "است", "بر"),
        doc_text="توزيع درآمد شركت بر اساس محصول در جدول آمده است.",
    ),
    GoldenQuery(
        query="کارایی عملیات فروش شرکت را توضیح بده",
        language="persian",
        must_include=("کارایی", "عملیات", "فروش", "شرکت"),
        must_exclude=("را",),
        doc_text="مدیریت کارایی عملیات فروش شركت را توضیح داد.",
    ),
    GoldenQuery(
        query="مهم‌ترین دارایی‌های شرکت چیست؟",
        language="persian",
        must_include=("دارایی‌های", "شرکت"),
        must_exclude=("چیست",),
        doc_text="مهم‌ترین دارايی‌های شركت در ترازنامه آمده است.",
    ),
    GoldenQuery(
        query="وضعیت نقدینگی شرکت در پایان سال چطور بود؟",
        language="persian",
        must_include=("وضعیت", "نقدینگی", "پایان"),
        must_exclude=("چطور", "بود", "در"),
        doc_text="وضعيت نقدینگی شركت در پایان سال مالي قوی بود.",
    ),
    GoldenQuery(
        query="شرکت چه تعداد کارمند دارد؟",
        language="persian",
        must_include=("تعداد", "کارمند", "شرکت"),
        must_exclude=("چه",),
        doc_text="شركت تعداد كارمند خود دارد و در گزارش ذكر كرده است.",
    ),
    GoldenQuery(
        query="ریسک ارز و نرخ بهره چیست؟",
        language="persian",
        must_include=("ریسک", "ارز", "نرخ", "بهره"),
        must_exclude=("چیست", "و"),
        doc_text="ريسك ارز و نرخ بهره در بخش عوامل ریسك توضیح داده شده است.",
    ),
    GoldenQuery(
        query="درآمد فروش اینترنت اشیا چقدر بوده؟",
        language="persian",
        must_include=("درآمد", "فروش", "اینترنت", "اشیا"),
        must_exclude=("چقدر", "بوده"),
        doc_text="درآمد فروش اینترنت اشیا شركت رشد كرد.",
    ),
    GoldenQuery(
        query="خلاصه بحث مدیریت مورد چشم‌انداز بلندمدت را بگو",
        language="persian",
        must_include=("خلاصه", "بحث", "مدیریت"),
        must_exclude=("را",),
    ),
)

ENGLISH_QUERIES: tuple[GoldenQuery, ...] = (
    GoldenQuery(
        query="What are Microsoft's major risks?",
        language="english",
        must_include=("Microsoft", "risks"),
    ),
    GoldenQuery(
        query="How did revenue change?",
        language="english",
        must_include=("revenue", "change"),
    ),
    GoldenQuery(
        query="Describe Apple cloud capacity plans",
        language="english",
        must_include=("Apple", "cloud", "capacity"),
    ),
    GoldenQuery(
        query="iPhone Services revenue mix",
        language="english",
        must_include=("iPhone", "Services", "revenue", "mix"),
    ),
    GoldenQuery(
        query="Data center demand drivers",
        language="english",
        must_include=("Data", "center", "demand"),
    ),
    GoldenQuery(
        query="customer concentration risks",
        language="english",
        must_include=("customer", "concentration"),
    ),
    GoldenQuery(
        query="AI infrastructure spending",
        language="english",
        must_include=("AI", "infrastructure"),
    ),
    GoldenQuery(
        query="Azure growth outlook",
        language="english",
        must_include=("Azure", "growth"),
    ),
    GoldenQuery(
        query="NVIDIA demand",
        language="english",
        must_include=("NVIDIA",),
    ),
    GoldenQuery(
        query="wearables revenue decline",
        language="english",
        must_include=("wearables", "revenue"),
    ),
)

MIXED_QUERIES: tuple[GoldenQuery, ...] = (
    GoldenQuery(
        query="ریسک‌های Microsoft در سال 2024 چیست؟",
        language="mixed",
        must_include=("ریسک‌های", "Microsoft", "2024"),
        must_exclude=("چیست", "در"),
        doc_text="ریسك‌های Microsoft در سال ۲۰۲۴ در گزارش ۱۰-K شرح داده شده است.",
    ),
    GoldenQuery(
        query="AWS چه تأثیری روی revenue شرکت داشته؟",
        language="mixed",
        must_include=("AWS", "revenue", "شرکت", "تأثیری"),
        must_exclude=("چه", "روی"),
        doc_text="سهم AWS از revenue شركت تأثیری پایدار داشته است.",
    ),
    GoldenQuery(
        query="در 10-K 2024 وضعیت cloud revenue چگونه بوده؟",
        language="mixed",
        must_include=("10-K", "2024", "وضعیت", "cloud", "revenue"),
        must_exclude=("چگونه", "بوده", "در"),
        doc_text="در ۱۰-K سال ۲۰۲۴ وضعیت cloud revenue شركت بهبود یافت.",
    ),
    GoldenQuery(
        query="مهم‌ترین risks شرکت چیست؟",
        language="mixed",
        must_include=("مهم‌ترین", "risks", "شرکت"),
        must_exclude=("چیست",),
        doc_text="مهم‌ترین risks شركت در بخش Risk Factors آمده است.",
    ),
    GoldenQuery(
        query="تأثیر نرخ بهره روی Operating Margin چیست؟",
        language="mixed",
        must_include=("تأثیر", "نرخ", "بهره", "Operating", "Margin"),
        must_exclude=("چیست", "روی"),
        doc_text="نرخ بهره بر Operating Margin شركت تأثیر گذاشت.",
    ),
    GoldenQuery(
        query="درآمد iPhone در سه‌ماهه دوم چقدر بود؟",
        language="mixed",
        must_include=("درآمد", "iPhone", "سه‌ماهه", "دوم"),
        must_exclude=("چقدر", "بود", "در"),
        doc_text="درآمد iPhone شركت در سه‌ماهه دوم رشد كرد.",
    ),
    GoldenQuery(
        query="رقابت Amazon در بازار cloud چیست؟",
        language="mixed",
        must_include=("رقابت", "Amazon", "بازار", "cloud"),
        must_exclude=("چیست", "در"),
        doc_text="رقابت Amazon در بازار cloud فشرده است.",
    ),
    GoldenQuery(
        query="خلاصه 10-K اپل را بگو",
        language="mixed",
        must_include=("خلاصه", "10-K", "اپل"),
        must_exclude=("را",),
    ),
    GoldenQuery(
        query="سهم Azure از درآمد کل چقدر است؟",
        language="mixed",
        must_include=("سهم", "Azure", "درآمد", "کل"),
        must_exclude=("چقدر", "است", "از"),
        doc_text="سهم Azure از درآمد كل شركت رشد كرد.",
    ),
    GoldenQuery(
        query="ریسک‌های supply chain در 10-K چیست؟",
        language="mixed",
        must_include=("ریسک‌های", "supply", "chain", "10-K"),
        must_exclude=("چیست", "در"),
        doc_text="ریسك‌های supply chain شركت در ۱۰-K توضیح داده شده است.",
    ),
)

ALL_QUERIES: tuple[GoldenQuery, ...] = (
    PERSIAN_QUERIES + ENGLISH_QUERIES + MIXED_QUERIES
)
