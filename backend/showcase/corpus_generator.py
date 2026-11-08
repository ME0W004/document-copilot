"""Deterministic synthetic demo corpus generator for Showcase Mode (Sprint 5.5).

Generates 4 realistic demo PDF documents:
1. 01_annual_report_fa.pdf (گزارش عملکرد سالانه ۱۴۰۴)
2. 02_financial_summary_en.pdf (Alborz Pioneer Tech - Financial Summary 2025)
3. 03_strategy_mixed.pdf (گزارش استراتژی و تحول دیجیتال — Strategy & Digital Transformation 2025-2026)
4. 04_hr_performance_fa.pdf (گزارش عملکرد منابع انسانی و سرمایه سازمانی ۱۴۰۴)

Each PDF contains proper logical text layers with Vazirmatn font / Helvetica,
preserving page provenance, Persian ZWNJ, and tables.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tests.fixtures.documents.generate_fixtures import (
    FONT_PATH,
    FontResource,
    PageContent,
    build_pdf,
)

SHOWCASE_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "showcase_corpus"


@dataclass(frozen=True)
class ShowcaseDocumentDef:
    filename: str
    title: str
    source_format: str
    language: str
    pages_count: int
    summary: str


SHOWCASE_SPECS: list[ShowcaseDocumentDef] = [
    ShowcaseDocumentDef(
        filename="01_annual_report_fa.pdf",
        title="گزارش عملکرد سالانه ۱۴۰۴",
        source_format="pdf",
        language="fa",
        pages_count=3,
        summary="تحلیل عملکرد مالی و عملیاتی شرکت، بررسی علل کاهش سود عملیاتی، و صورت‌های سود و زیان سالانه.",
    ),
    ShowcaseDocumentDef(
        filename="02_financial_summary_en.pdf",
        title="Alborz Pioneer Tech - Financial Summary 2025",
        source_format="pdf",
        language="en",
        pages_count=2,
        summary="Annual financial summary in English covering statements of operations, segment revenue, and capital expenditure.",
    ),
    ShowcaseDocumentDef(
        filename="03_strategy_mixed.pdf",
        title="گزارش استراتژی و تحول دیجیتال — Strategy & Digital Transformation 2025-2026",
        source_format="pdf",
        language="mixed",
        pages_count=2,
        summary="سند استراتژی تحول دیجیتال و پیاده‌سازی سیستم‌های LLM، معماری ابری و شاخص‌های کلیدی SLA.",
    ),
    ShowcaseDocumentDef(
        filename="04_hr_performance_fa.pdf",
        title="گزارش عملکرد منابع انسانی و سرمایه سازمانی ۱۴۰۴",
        source_format="pdf",
        language="fa",
        pages_count=2,
        summary="گزارش سرمایه انسانی، توزیع نیروهای فنی، نرخ نگه‌داشت ۸۹ درصدی متخصصان و شاخص‌های بهره‌وری.",
    ),
]


def _render_page_header(page: PageContent, font: FontResource, title: str, doc_name: str, page_num: int) -> None:
    page.line_rtl(font, title, 545, 800, 14.0)
    page.line_rtl(font, f"سند آزمایشی شرکت فناوری پیشگامان البرز | {doc_name}", 545, 782, 8.5)
    page.line_rtl(font, f"صفحه {page_num}", 80, 800, 8.5)
    page.ops.append("0.85 0.85 0.85 RG 0.5 w 50 770 m 545 770 l S")


def _render_page_header_en(page: PageContent, title: str, doc_name: str, page_num: int) -> None:
    page.line_ltr(title, 50, 800, 14.0)
    page.line_ltr(f"Synthetic Document - Alborz Pioneer Tech | {doc_name}", 50, 782, 8.5)
    page.line_ltr(f"Page {page_num}", 510, 800, 8.5)
    page.ops.append("0.85 0.85 0.85 RG 0.5 w 50 770 m 545 770 l S")


def generate_annual_report_fa(font: FontResource, output_path: Path) -> None:
    # Page 1
    p1 = PageContent()
    _render_page_header(p1, font, "گزارش عملکرد سالانه ۱۴۰۴", "خلاصه مالی و عملیاتی", 1)

    y = 740
    p1.line_rtl(font, "۱. خلاصه عملکرد مالی و سودآوری شرکت", 545, y, 12.0)
    y -= 25
    p1.line_rtl(font, "در سال مالی ۱۴۰۴، درآمد کل شرکت با رشد ۲۴ درصدی به مبلغ ۱۸۵ میلیارد تومان رسید.", 545, y, 9.5)
    y -= 18
    p1.line_rtl(font, "با این وجود، سود عملیاتی شرکت از ۴۲ میلیارد تومان در سال ۱۴۰۳ به ۳۱ میلیارد تومان کاهش یافت.", 545, y, 9.5)
    y -= 18
    p1.line_rtl(font, "حاشیه سود عملیاتی شرکت از ۲۸.۲ درصد به ۱۶.۷ درصد کاهش یافته است.", 545, y, 9.5)

    y -= 30
    p1.line_rtl(font, "۲. مهم‌ترین عوامل کاهش سود عملیاتی در سال ۱۴۰۴", 545, y, 11.5)
    y -= 22
    p1.line_rtl(font, "بر اساس بررسی تفصیلی صورت‌های مالی، مهم‌ترین عوامل کاهش سود عملیاتی عبارتند از:", 545, y, 9.5)
    y -= 18
    p1.line_rtl(font, "۱. افزایش ۲۸ درصدی هزینه‌های زیرساخت ابری و سرورهای پردازشی هوش مصنوعی در طول سال.", 545, y, 9.5)
    y -= 18
    p1.line_rtl(font, "۲. افزایش هزینه‌های حقوق، دستمزد و جذب نخبگان حوزه نرم‌افزار به علت رقابت شدید بازار کار.", 545, y, 9.5)
    y -= 18
    p1.line_rtl(font, "۳. نوسانات شدید نرخ ارز که بهای تمام‌شده تجهیزات شبکه و ذخیره‌سازی را افزایش داده است.", 545, y, 9.5)
    y -= 18
    p1.line_rtl(font, "۴. افزایش هزینه‌های سربار اداری و توسعه شعب استانی در دو شهر مشهد و اصفهان.", 545, y, 9.5)

    y -= 35
    p1.line_rtl(font, "جدول خلاصه شاخص‌های مالی شرکت (ارقام به میلیارد تومان):", 545, y, 10.0)
    y -= 20
    p1.line_rtl(font, "شاخص مالی | عملکرد سال ۱۴۰۳ | عملکرد سال ۱۴۰۴ | درصد تغییر سالانه", 545, y, 9.0)
    y -= 16
    p1.line_rtl(font, "درآمد عملیاتی کل | ۱۴۹ میلیارد تومان | ۱۸۵ میلیارد تومان | ۲۴+ درصد", 545, y, 9.0)
    y -= 16
    p1.line_rtl(font, "سود ناخالص | ۶۱ میلیارد تومان | ۶۷ میلیارد تومان | ۱۰+ درصد", 545, y, 9.0)
    y -= 16
    p1.line_rtl(font, "سود عملیاتی | ۴۲ میلیارد تومان | ۳۱ میلیارد تومان | ۲۶- درصد", 545, y, 9.0)
    y -= 16
    p1.line_rtl(font, "حاشیه سود ناخالص | ۴۰.۹ درصد | ۳۶.۲ درصد | ۴.۷- درصد", 545, y, 9.0)
    y -= 16
    p1.line_rtl(font, "حاشیه سود عملیاتی | ۲۸.۲ درصد | ۱۶.۷ درصد | ۱۱.۵- درصد", 545, y, 9.0)

    # Page 2
    p2 = PageContent()
    _render_page_header(p2, font, "گزارش عملکرد سالانه ۱۴۰۴", "تحلیل بخش‌های تجاری", 2)
    y = 740
    p2.line_rtl(font, "۳. تفکیک عملکرد بخش‌های تجاری", 545, y, 12.0)
    y -= 25
    p2.line_rtl(font, "فعالیت شرکت در دو بخش اصلی سازمان‌دهی شده است:", 545, y, 9.5)
    y -= 20
    p2.line_rtl(font, "الف) بخش خدمات ابری و زیرساخت داده (Cloud & Data Services):", 545, y, 10.5)
    y -= 18
    p2.line_rtl(font, "درآمد این بخش با ۳۵ درصد رشد به ۱۱۰ میلیارد تومان رسید که ۵۹ درصد کل درآمد شرکت را تشکیل می‌دهد.", 545, y, 9.5)
    y -= 18
    p2.line_rtl(font, "به دلیل ارتقای پهنای باند و سرمایه‌گذاری سنگین در امنیت شبکه، حاشیه سود این بخش از ۳۳٪ به ۲۱٪ کاهش یافت.", 545, y, 9.5)
    y -= 22
    p2.line_rtl(font, "ب) بخش راهکارهای هوش مصنوعی و نرم‌افزار سازمانی (Enterprise AI):", 545, y, 10.5)
    y -= 18
    p2.line_rtl(font, "درآمد این بخش ۷۵ میلیارد تومان ثبت شد. قراردادهای اشتراک سالانه (SaaS) ۶۰ درصد درآمد این بخش را ساختند.", 545, y, 9.5)
    y -= 18
    p2.line_rtl(font, "نرخ تمدید سالانه مشتریان سازمانی به ۹۴ درصد ارتقا یافته است که نشان‌دهنده رضایت بالای مشتریان است.", 545, y, 9.5)

    # Page 3
    p3 = PageContent()
    _render_page_header(p3, font, "گزارش عملکرد سالانه ۱۴۰۴", "مدیریت ریسک و چشم‌انداز", 3)
    y = 740
    p3.line_rtl(font, "۴. ریسک‌های عمده و اقدامات اصلاحی", 545, y, 12.0)
    y -= 25
    p3.line_rtl(font, "شرکت برای مهار رشد هزینه‌های عملیاتی سه اقدام راهبردی را آغاز کرده است:", 545, y, 9.5)
    y -= 18
    p3.line_rtl(font, "۱. مهاجرت به معماری ترکیبی ابری (Hybrid Cloud) جهت کاهش اتکا به تأمین‌کنندگان خارجی سرور.", 545, y, 9.5)
    y -= 18
    p3.line_rtl(font, "۲. راه‌اندازی مرکز داده اختصاصی در منطقه ویژه اقتصادی پیام تا پایان شش‌ماهه اول ۱۴۰۵.", 545, y, 9.5)
    y -= 18
    p3.line_rtl(font, "۳. خودکارسازی فرآیندهای استقرار مدل‌های زبانی جهت کاهش هزینه‌های نگه‌داری نرم‌افزار.", 545, y, 9.5)
    y -= 25
    p3.line_rtl(font, "برآورد مدیریت حاکی از آن است که این اقدامات موجب صرفه‌جویی ۲۰ میلیارد تومانی در سال ۱۴۰۵ خواهد شد.", 545, y, 9.5)

    build_pdf([p1, p2, p3], output_path, font=font)


def generate_financial_summary_en(output_path: Path) -> None:
    # Page 1
    p1 = PageContent()
    _render_page_header_en(p1, "Financial Summary 2025", "Consolidated Operations", 1)
    y = 740
    p1.line_ltr("1. Consolidated Statements of Operations", 50, y, 12.0)
    y -= 25
    p1.line_ltr("For the fiscal year ended December 31, 2025, total revenue was $42.5 million,", 50, y, 9.5)
    y -= 18
    p1.line_ltr("compared to $34.2 million in fiscal year 2024, representing an increase of 24.3%.", 50, y, 9.5)
    y -= 18
    p1.line_ltr("Operating income was $8.2 million in 2025 compared to $10.5 million in 2024.", 50, y, 9.5)
    y -= 18
    p1.line_ltr("The reduction in operating margin from 30.7% to 19.3% was primarily driven by", 50, y, 9.5)
    y -= 18
    p1.line_ltr("elevated GPU computing cluster lease expenses and increased talent acquisition costs.", 50, y, 9.5)

    y -= 30
    p1.line_ltr("Table: Key Financial Metrics (in USD Millions)", 50, y, 10.5)
    y -= 20
    p1.line_ltr("Financial Metric | FY 2024 | FY 2025 | YoY Change", 50, y, 9.0)
    y -= 16
    p1.line_ltr("Total Revenue | $34.2M | $42.5M | +24.3%", 50, y, 9.0)
    y -= 16
    p1.line_ltr("Gross Profit | $22.1M | $24.8M | +12.2%", 50, y, 9.0)
    y -= 16
    p1.line_ltr("Operating Income | $10.5M | $8.2M | -21.9%", 50, y, 9.0)
    y -= 16
    p1.line_ltr("R&D Expenditures | $8.4M | $12.1M | +44.0%", 50, y, 9.0)
    y -= 16
    p1.line_ltr("Operating Cash Flow | $7.8M | $6.4M | -17.9%", 50, y, 9.0)

    # Page 2
    p2 = PageContent()
    _render_page_header_en(p2, "Financial Summary 2025", "Segment Analysis & CapEx", 2)
    y = 740
    p2.line_ltr("2. Segment Performance & Capital Investments", 50, y, 12.0)
    y -= 25
    p2.line_ltr("The Enterprise SaaS segment generated $25.8 million, up 28.0% year-over-year,", 50, y, 9.5)
    y -= 18
    p2.line_ltr("reflecting strong market adoption of the Document Copilot enterprise edition.", 50, y, 9.5)
    y -= 18
    p2.line_ltr("Cloud Infrastructure services contributed $16.7 million, representing 39.3% of revenue.", 50, y, 9.5)
    y -= 25
    p2.line_ltr("Capital expenditures totaled $5.4 million for the year, focusing on:", 50, y, 9.5)
    y -= 18
    p2.line_ltr("- High-performance GPU inference servers for on-premises enterprise deployments.", 50, y, 9.5)
    y -= 18
    p2.line_ltr("- Low-latency network interconnects between Tehran and regional data availability zones.", 50, y, 9.5)
    y -= 18
    p2.line_ltr("- SOC 2 Type II compliance audits and international security certifications.", 50, y, 9.5)

    build_pdf([p1, p2], output_path, font=None)


def generate_strategy_mixed(font: FontResource, output_path: Path) -> None:
    # Page 1
    p1 = PageContent()
    _render_page_header(p1, font, "گزارش استراتژی و تحول دیجیتال", "Strategy & Digital Transformation", 1)
    y = 740
    p1.line_rtl(font, "۱. معماری فناوری و ادغام سیستم‌ها (Technology Architecture)", 545, y, 11.5)
    y -= 25
    p1.line_rtl(font, "سند استراتژی پیشگامان البرز برای سال‌های ۲۰۲۵ تا ۲۰۲۶ بر سه محور کلیدی استوار است:", 545, y, 9.5)
    y -= 18
    p1.line_rtl(font, "۱. استقرار معماری Cloud Native و پایگاه داده توزیع‌شده با استفاده از Supabase و PostgreSQL.", 545, y, 9.5)
    y -= 18
    p1.line_rtl(font, "۲. پیاده‌سازی مدل‌های بازیابی ترکیبی (Hybrid Retrieval: RRF + pgvector) برای اسناد دو زبانه.", 545, y, 9.5)
    y -= 18
    p1.line_rtl(font, "۳. اتصال ایمن به APIهای OpenAI با حفظ استانداردهای حریم خصوصی و امنیت داده‌های مشتریان.", 545, y, 9.5)
    y -= 25
    p1.line_rtl(font, "توسعه محصول Document Copilot امکان پردازش سازمانی اسناد فارسی و انگلیسی را با دقت بالا فراهم کرده است.", 545, y, 9.5)

    # Page 2
    p2 = PageContent()
    _render_page_header(p2, font, "گزارش استراتژی و تحول دیجیتال", "Key Performance Indicators", 2)
    y = 740
    p2.line_rtl(font, "۲. شاخص‌های کلیدی عملکرد و توافق‌نامه سطح خدمات (SLA)", 545, y, 11.5)
    y -= 25
    p2.line_rtl(font, "اهداف عملکردی تعیین‌شده برای سال آینده شامل موارد زیر است:", 545, y, 9.5)
    y -= 18
    p2.line_rtl(font, "الف) پایداری و دسترسی‌پذیری سیستم (Uptime SLA) به میزان ۹۹.۹۵ درصد تضمین می‌گردد.", 545, y, 9.5)
    y -= 18
    p2.line_rtl(font, "ب) میانگین زمان پاسخگویی به درخواست‌های جستجوی اسناد (P95 Latency) زیر ۳۵۰ میلی‌ثانیه تثبیت می‌شود.", 545, y, 9.5)
    y -= 18
    p2.line_rtl(font, "ج) گسترش مشتریان فعال بخش سازمانی از ۷۵ سازمان به بیش از ۱۲۰ سازمان دولتی و خصوصی.", 545, y, 9.5)
    y -= 18
    p2.line_rtl(font, "د) پیاده‌سازی سازوکار اعتبارسنجی دقیق استنادها (Citation Grounding) برای حذف خطاهای احتمالی.", 545, y, 9.5)

    build_pdf([p1, p2], output_path, font=font)


def generate_hr_performance_fa(font: FontResource, output_path: Path) -> None:
    # Page 1
    p1 = PageContent()
    _render_page_header(p1, font, "گزارش عملکرد منابع انسانی و سرمایه سازمانی ۱۴۰۴", "آمار پرسنل و حفظ نخبگان", 1)
    y = 740
    p1.line_rtl(font, "۱. آمار سرمایه انسانی و ترکیب تخصصی تیم‌ها", 545, y, 11.5)
    y -= 25
    p1.line_rtl(font, "در پایان سال مالی ۱۴۰۴، تعداد همکاران تمام‌وقت شرکت به ۴۸۰ نفر رسید که رشد ۱۸ درصدی را نشان می‌دهد.", 545, y, 9.5)
    y -= 18
    p1.line_rtl(font, "ترکیب تخصصی همکاران به شرح زیر است: ۶۲ درصد در بخش مهندسی نرم‌افزار، هوش مصنوعی و زیرساخت،", 545, y, 9.5)
    y -= 18
    p1.line_rtl(font, "۲۳ درصد در بخش بازاریابی و فروش سازمانی، و ۱۵ درصد در بخش مالی و پشتیبانی فعالیت می‌کنند.", 545, y, 9.5)
    y -= 25
    p1.line_rtl(font, "نرخ نگه‌داشت نخبگان و نیروهای کلیدی شرکت به ۸۹ درصد رسید که نشان‌دهنده محیط کاری رضایت‌بخش است.", 545, y, 9.5)

    # Page 2
    p2 = PageContent()
    _render_page_header(p2, font, "گزارش عملکرد منابع انسانی و سرمایه سازمانی ۱۴۰۴", "آموزش و توسعه شایستگی‌ها", 2)
    y = 740
    p2.line_rtl(font, "۲. توانمندسازی، آموزش و ارزیابی عملکرد", 545, y, 11.5)
    y -= 25
    p2.line_rtl(font, "در طول سال ۱۴۰۴ بیش از ۱۲,۴۰۰ نفر-ساعت آموزش تخصصی برای کارکنان برگزار گردید.", 545, y, 9.5)
    y -= 18
    p2.line_rtl(font, "دوره‌های آموزشی متمرکز بر هوش مصنوعی مولد، استانداردهای تست نرم‌افزار و امنیت داده‌ها بوده است.", 545, y, 9.5)
    y -= 18
    p2.line_rtl(font, "ارزیابی ۳۶۰ درجه عملکرد برای ۹۵ درصد همکاران انجام شد و ۳۰ درصد ارتقاهای مدیریتی از داخل سازمان صورت گرفت.", 545, y, 9.5)

    build_pdf([p1, p2], output_path, font=font)


def generate_all_showcase_documents(target_dir: Path | None = None) -> list[Path]:
    out_dir = target_dir or SHOWCASE_DATA_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    font = FontResource(FONT_PATH)

    paths: list[Path] = []

    p1 = out_dir / "01_annual_report_fa.pdf"
    generate_annual_report_fa(font, p1)
    paths.append(p1)

    p2 = out_dir / "02_financial_summary_en.pdf"
    generate_financial_summary_en(p2)
    paths.append(p2)

    p3 = out_dir / "03_strategy_mixed.pdf"
    generate_strategy_mixed(font, p3)
    paths.append(p3)

    p4 = out_dir / "04_hr_performance_fa.pdf"
    generate_hr_performance_fa(font, p4)
    paths.append(p4)

    return paths


if __name__ == "__main__":
    generated = generate_all_showcase_documents()
    print(f"Generated {len(generated)} showcase documents in {SHOWCASE_DATA_DIR}:")
    for p in generated:
        print(f" - {p.name} ({p.stat().st_size} bytes)")
