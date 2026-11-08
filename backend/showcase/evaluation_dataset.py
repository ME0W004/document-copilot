"""Deterministic 30-case evaluation dataset for Showcase Mode (Sprint 5.5).

Categories:
- Persian factual (8)
- English factual (5)
- Mixed-language (5)
- Multi-document (5)
- Multi-chunk reasoning (3)
- Unanswerable / grounding rejection (4)
TOTAL: 30
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class EvaluationCase:
    id: str
    query: str
    category: Literal[
        "persian_factual",
        "english_factual",
        "mixed_language",
        "multi_document",
        "multi_chunk_reasoning",
        "unanswerable",
    ]
    language: Literal["fa", "en", "mixed"]
    is_answerable: bool
    target_docs: list[str] = field(default_factory=list)
    required_keywords: list[str] = field(default_factory=list)
    ground_truth_summary: str = ""


EVALUATION_DATASET: list[EvaluationCase] = [
    # --- Persian Factual (8 cases) ---
    EvaluationCase(
        id="EVAL-001",
        query="در سال مالی ۱۴۰۴ درآمد کل شرکت چقدر بوده است؟",
        category="persian_factual",
        language="fa",
        is_answerable=True,
        target_docs=["01_annual_report_fa.pdf"],
        required_keywords=["درآمد", "۱۸۵", "میلیارد", "۱۴۰۴"],
        ground_truth_summary="درآمد کل شرکت با رشد ۲۴ درصدی به مبلغ ۱۸۵ میلیارد تومان رسید.",
    ),
    EvaluationCase(
        id="EVAL-002",
        query="بر اساس گزارش عملکرد سال ۱۴۰۴، مهم‌ترین عوامل کاهش سود عملیاتی شرکت چه بوده است؟",
        category="persian_factual",
        language="fa",
        is_answerable=True,
        target_docs=["01_annual_report_fa.pdf"],
        required_keywords=["کاهش", "سود", "عملیاتی", "ابری", "۲۸"],
        ground_truth_summary="افزایش ۲۸ درصدی هزینه‌های زیرساخت ابری، افزایش هزینه‌های جذب نخبگان و نوسانات نرخ ارز.",
    ),
    EvaluationCase(
        id="EVAL-003",
        query="سود عملیاتی شرکت در سال ۱۴۰۴ در مقایسه با سال ۱۴۰۳ چه تغییری کرد؟",
        category="persian_factual",
        language="fa",
        is_answerable=True,
        target_docs=["01_annual_report_fa.pdf"],
        required_keywords=["سود", "عملیاتی", "۴۲", "۳۱"],
        ground_truth_summary="سود عملیاتی از ۴۲ میلیارد تومان در سال ۱۴۰۳ به ۳۱ میلیارد تومان (۲۶ درصد کاهش) رسید.",
    ),
    EvaluationCase(
        id="EVAL-004",
        query="حاشیه سود ناخالص شرکت در سال ۱۴۰۴ چند درصد گزارش شده است؟",
        category="persian_factual",
        language="fa",
        is_answerable=True,
        target_docs=["01_annual_report_fa.pdf"],
        required_keywords=["حاشیه", "سود", "ناخالص", "۳۶"],
        ground_truth_summary="حاشیه سود ناخالص در سال ۱۴۰۴ برابر ۳۶.۲ درصد گزارش شده است.",
    ),
    EvaluationCase(
        id="EVAL-005",
        query="درآمد بخش خدمات ابری و پردازش داده شرکت چقدر بوده است؟",
        category="persian_factual",
        language="fa",
        is_answerable=True,
        target_docs=["01_annual_report_fa.pdf"],
        required_keywords=["خدمات", "ابری", "۱۱۰", "میلیارد"],
        ground_truth_summary="درآمد بخش خدمات ابری با ۳۵ درصد رشد به ۱۱۰ میلیارد تومان رسید.",
    ),
    EvaluationCase(
        id="EVAL-006",
        query="تعداد کل همکاران تمام‌وقت شرکت در پایان سال ۱۴۰۴ چند نفر بوده است؟",
        category="persian_factual",
        language="fa",
        is_answerable=True,
        target_docs=["04_hr_performance_fa.pdf"],
        required_keywords=["همکاران", "۴۸۰", "نفر"],
        ground_truth_summary="تعداد کل همکاران تمام‌وقت شرکت در پایان سال ۱۴۰۴ به ۴۸۰ نفر رسید.",
    ),
    EvaluationCase(
        id="EVAL-007",
        query="چند درصد از نیروهای شرکت در بخش‌های فنی و مهندسی مشغول به کارند؟",
        category="persian_factual",
        language="fa",
        is_answerable=True,
        target_docs=["04_hr_performance_fa.pdf"],
        required_keywords=["درصد", "فنی", "۶۲"],
        ground_truth_summary="۶۲ درصد پرسنل در بخش‌های فنی، مهندسی نرم‌افزار و هوش مصنوعی مشغولند.",
    ),
    EvaluationCase(
        id="EVAL-008",
        query="نرخ نگه‌داشت نخبگان و نیروهای کلیدی شرکت در سال ۱۴۰۴ چقدر بوده است؟",
        category="persian_factual",
        language="fa",
        is_answerable=True,
        target_docs=["04_hr_performance_fa.pdf"],
        required_keywords=["نگه‌داشت", "نخبگان", "۸۹"],
        ground_truth_summary="نرخ نگه‌داشت متخصصان و نخبگان کلیدی شرکت ۸۹ درصد بوده است.",
    ),

    # --- English Factual (5 cases) ---
    EvaluationCase(
        id="EVAL-009",
        query="What was the total consolidated revenue of the company in fiscal year 2025?",
        category="english_factual",
        language="en",
        is_answerable=True,
        target_docs=["02_financial_summary_en.pdf"],
        required_keywords=["revenue", "42.5", "million"],
        ground_truth_summary="Total consolidated revenue was $42.5 million, up 24.3% YoY.",
    ),
    EvaluationCase(
        id="EVAL-010",
        query="How much operating income was reported in 2025 compared to 2024?",
        category="english_factual",
        language="en",
        is_answerable=True,
        target_docs=["02_financial_summary_en.pdf"],
        required_keywords=["operating", "income", "8.2", "10.5"],
        ground_truth_summary="Operating income was $8.2 million in 2025 compared to $10.5 million in 2024.",
    ),
    EvaluationCase(
        id="EVAL-011",
        query="What factors drove the reduction in operating margin in the financial summary?",
        category="english_factual",
        language="en",
        is_answerable=True,
        target_docs=["02_financial_summary_en.pdf"],
        required_keywords=["GPU", "cluster", "lease", "talent"],
        ground_truth_summary="Elevated GPU computing cluster lease expenses and talent acquisition costs.",
    ),
    EvaluationCase(
        id="EVAL-012",
        query="How much revenue did the Enterprise SaaS segment generate in 2025?",
        category="english_factual",
        language="en",
        is_answerable=True,
        target_docs=["02_financial_summary_en.pdf"],
        required_keywords=["Enterprise", "SaaS", "25.8", "million"],
        ground_truth_summary="Enterprise SaaS revenue reached $25.8 million, up 28.0% YoY.",
    ),
    EvaluationCase(
        id="EVAL-013",
        query="What was the total capital expenditure in 2025 and what were the priority areas?",
        category="english_factual",
        language="en",
        is_answerable=True,
        target_docs=["02_financial_summary_en.pdf"],
        required_keywords=["5.4", "GPU", "servers", "network"],
        ground_truth_summary="CapEx was $5.4 million for GPU inference servers, network interconnects, and SOC 2 audits.",
    ),

    # --- Mixed-Language (5 cases) ---
    EvaluationCase(
        id="EVAL-014",
        query="معماری فناوری و سیستم‌های شرکت بر چه پلتفرم‌ها و دیتابیس‌هایی استوار است؟",
        category="mixed_language",
        language="mixed",
        is_answerable=True,
        target_docs=["03_strategy_mixed.pdf"],
        required_keywords=["Cloud", "Native", "Supabase", "PostgreSQL", "RRF"],
        ground_truth_summary="معماری Cloud Native مبتنی بر Supabase و PostgreSQL با جستجوی ترکیبی RRF و pgvector.",
    ),
    EvaluationCase(
        id="EVAL-015",
        query="پایداری سرویس و توافق‌نامه سطح خدمات (Uptime SLA) شرکت چند درصد تضمین شده است؟",
        category="mixed_language",
        language="mixed",
        is_answerable=True,
        target_docs=["03_strategy_mixed.pdf"],
        required_keywords=["SLA", "۹۹.۹۵", "پایداری"],
        ground_truth_summary="پایداری و دسترسی‌پذیری سیستم (Uptime SLA) به میزان ۹۹.۹۵ درصد تضمین شده است.",
    ),
    EvaluationCase(
        id="EVAL-016",
        query="میانگین زمان پاسخگویی P95 Latency برای جستجوهای متنی و معنایی در سیستم چقدر هدف‌گذاری شده است؟",
        category="mixed_language",
        language="mixed",
        is_answerable=True,
        target_docs=["03_strategy_mixed.pdf"],
        required_keywords=["Latency", "۳۵۰", "میلی‌ثانیه"],
        ground_truth_summary="میانگین زمان پاسخگویی P95 زیر ۳۵۰ میلی‌ثانیه تثبیت می‌شود.",
    ),
    EvaluationCase(
        id="EVAL-017",
        query="تعداد مشتریان بخش Enterprise Solutions تا پایان سال ۲۰۲۶ چند سازمان هدف‌گذاری شده است؟",
        category="mixed_language",
        language="mixed",
        is_answerable=True,
        target_docs=["03_strategy_mixed.pdf"],
        required_keywords=["Enterprise", "۱۲۰", "سازمان"],
        ground_truth_summary="افزایش مشتریان سازمانی فعال به بیش از ۱۲۰ سازمان دولتی و خصوصی.",
    ),
    EvaluationCase(
        id="EVAL-018",
        query="استقرار سامانه Document Copilot چه اثری بر سرعت پاسخگویی به تحلیل‌های اسناد داشته است؟",
        category="mixed_language",
        language="mixed",
        is_answerable=True,
        target_docs=["03_strategy_mixed.pdf"],
        required_keywords=["Document", "Copilot", "۳", "برابر"],
        ground_truth_summary="نرخ پاسخگویی به درخواست‌های تحلیلی را ۳ برابر سریع‌تر کرده است.",
    ),

    # --- Multi-Document (5 cases) ---
    EvaluationCase(
        id="EVAL-019",
        query="درآمد بخش راهکارهای سازمانی در گزارش سالانه فارسی و گزارش مالی انگلیسی چگونه گزارش شده است؟",
        category="multi_document",
        language="mixed",
        is_answerable=True,
        target_docs=["01_annual_report_fa.pdf", "02_financial_summary_en.pdf"],
        required_keywords=["۷۵", "میلیارد", "25.8", "million"],
        ground_truth_summary="۷۵ میلیارد تومان در گزارش فارسی و $25.8M در بخش Enterprise SaaS گزارش انگلیسی.",
    ),
    EvaluationCase(
        id="EVAL-020",
        query="هزینه‌های کلاستر سرورهای ابری در گزارش مالی و برنامه زیرساخت در سند استراتژی چه ارتباطی دارند؟",
        category="multi_document",
        language="mixed",
        is_answerable=True,
        target_docs=["01_annual_report_fa.pdf", "03_strategy_mixed.pdf"],
        required_keywords=["هزینه‌های", "ابری", "Hybrid", "Cloud"],
        ground_truth_summary="مهار رشد ۲۸ درصدی هزینه‌های ابری از طریق استقرار معماری ترکیبی Hybrid Cloud و دیتاسنتر پیام.",
    ),
    EvaluationCase(
        id="EVAL-021",
        query="نرخ تمدید قراردادهای مشتریان و برنامه گسترش بازار سازمانی در اسناد شرکت چگونه منعکس شده است؟",
        category="multi_document",
        language="fa",
        is_answerable=True,
        target_docs=["01_annual_report_fa.pdf", "03_strategy_mixed.pdf"],
        required_keywords=["تمدید", "۹۴", "۱۲۰"],
        ground_truth_summary="نرخ تمدید ۹۴ درصدی مشتریان و ارتقای سازمان‌های هدف به ۱۲۰ مشتری تا پایان ۲۰۲۶.",
    ),
    EvaluationCase(
        id="EVAL-022",
        query="افزایش هزینه‌های جذب متخصصان در گزارش مالی و تعداد پرسنل فنی در گزارش منابع انسانی چه نسبتی دارند؟",
        category="multi_document",
        language="fa",
        is_answerable=True,
        target_docs=["01_annual_report_fa.pdf", "04_hr_performance_fa.pdf"],
        required_keywords=["جذب", "نخبگان", "۴۸۰", "۶۲"],
        ground_truth_summary="افزایش هزینه حقوق نیروهای فنی به عنوان عامل افت سود؛ ۴۸۰ نفر پرسنل با سهم ۶۲ درصدی فنی.",
    ),
    EvaluationCase(
        id="EVAL-023",
        query="سرمایه‌گذاری بر آموزش هوش مصنوعی در گزارش منابع انسانی و توسعه مدل‌های زبانی در سند استراتژی چیست؟",
        category="multi_document",
        language="fa",
        is_answerable=True,
        target_docs=["03_strategy_mixed.pdf", "04_hr_performance_fa.pdf"],
        required_keywords=["۱۲,۴۰۰", "آموزش", "زبان"],
        ground_truth_summary="برگزاری ۱۲,۴۰۰ نفر-ساعت آموزش هوش مصنوعی برای پشتیبانی از توسعه Document Copilot و LLMها.",
    ),

    # --- Multi-Chunk Reasoning (3 cases) ---
    EvaluationCase(
        id="EVAL-024",
        query="چرا با وجود رشد ۲۴ درصدی درآمد کل شرکت، سود عملیاتی سال ۱۴۰۴ با افت ۲۶ درصدی مواجه شد؟",
        category="multi_chunk_reasoning",
        language="fa",
        is_answerable=True,
        target_docs=["01_annual_report_fa.pdf"],
        required_keywords=["درآمد", "۲۴", "سود", "۲۶", "ابری", "۲۸"],
        ground_truth_summary="افزایش ۲۸ درصدی هزینه‌های پردازش ابری، افزایش حقوق متخصصان، نوسان ارز و توسعه شعب مشهد و اصفهان.",
    ),
    EvaluationCase(
        id="EVAL-025",
        query="برنامه شرکت برای بازگرداندن حاشیه سود عملیاتی به بالای ۲۲ درصد در سال ۱۴۰۵ شامل چه مراحلی است؟",
        category="multi_chunk_reasoning",
        language="fa",
        is_answerable=True,
        target_docs=["01_annual_report_fa.pdf"],
        required_keywords=["۲۲", "درصد", "مرکز", "داده", "پیام", "۲۰"],
        ground_truth_summary="مهاجرت به معماری ترکیبی و بهره‌برداری از مرکز داده اختصاصی پیام با ۲۰ میلیارد تومان صرفه‌جویی.",
    ),
    EvaluationCase(
        id="EVAL-026",
        query="تأثیر مدل اشتراک سالانه (SaaS) بر پایداری جریان درآمدی و توزیع نیروهای فنی شرکت چیست؟",
        category="multi_chunk_reasoning",
        language="fa",
        is_answerable=True,
        target_docs=["01_annual_report_fa.pdf", "04_hr_performance_fa.pdf"],
        required_keywords=["SaaS", "۶۰", "۹۴", "۶۲"],
        ground_truth_summary="سهم ۶۰ درصدی مدل SaaS، نرخ تمدید ۹۴ درصدی، و تخصیص ۶۲ درصد پرسنل به تیم‌های مهندسی و هوش مصنوعی.",
    ),

    # --- Unanswerable / Grounding Rejection (4 cases) ---
    EvaluationCase(
        id="EVAL-027",
        query="سود خالص شرکت پس از کسر مالیات در سال ۱۴۰۴ دقیقاً چقدر بوده است؟",
        category="unanswerable",
        language="fa",
        is_answerable=False,
        target_docs=["01_annual_report_fa.pdf"],
        required_keywords=["مالیات", "خالص"],
        ground_truth_summary="اطلاعات سود خالص پس از مالیات در اسناد موجود نیست (فقط سود ناخالص و عملیاتی ذکر شده).",
    ),
    EvaluationCase(
        id="EVAL-028",
        query="آدرس دقیق شعبه شرکت در کشور امارات و دبی چیست؟",
        category="unanswerable",
        language="fa",
        is_answerable=False,
        target_docs=[],
        required_keywords=["امارات", "دبی"],
        ground_truth_summary="شرکت فاقد شعبه در امارات است (تنها شعب مشهد و اصفهان در اسناد ذکر شده‌اند).",
    ),
    EvaluationCase(
        id="EVAL-029",
        query="What was the total dividend per share distributed to common shareholders in 2025?",
        category="unanswerable",
        language="en",
        is_answerable=False,
        target_docs=["02_financial_summary_en.pdf"],
        required_keywords=["dividend", "share"],
        ground_truth_summary="No dividend per share information is contained in the financial summary.",
    ),
    EvaluationCase(
        id="EVAL-030",
        query="شرکت از چه مدل کوانتومی برای رمزنگاری تراکنش‌های بانکی خود استفاده می‌کند؟",
        category="unanswerable",
        language="fa",
        is_answerable=False,
        target_docs=[],
        required_keywords=["کوانتومی", "رمزنگاری"],
        ground_truth_summary="ادعای ساختگی خارج از دامنه؛ هیچ‌گونه فناوری کوانتومی در اسناد ذکر نشده است.",
    ),
]
