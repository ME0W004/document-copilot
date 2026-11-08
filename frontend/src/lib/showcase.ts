import { env } from '@/lib/env'

export type ShowcaseDocument = {
  id: string
  filename: string
  title: string
  source_format: string
  language: string
  pages_count: number
  chunks_count: number
  is_indexed: boolean
  summary: string
  file_path: string
  ingested_at: string
}

export type ShowcaseOverviewResponse = {
  status: string
  total_documents: number
  total_chunks: number
  indexed_at: string
  documents: ShowcaseDocument[]
}

export type ShowcaseCitation = {
  citation_index: number
  document_id: string
  document_title: string
  document_format: string
  page: string
  chunk_id: string
  chunk_index: number
  excerpt: string
  role: string
}

export type ShowcaseTraceStep = {
  step: string
  status: string
  label: string
  detail: string
  elapsed_ms: number
}

export type ShowcaseAnalysisResponse = {
  question: string
  answer: string
  citations: ShowcaseCitation[]
  analysis_trace: ShowcaseTraceStep[]
  model_info: {
    llm_model: string
    embedding_model: string
    grounding_model: string
    executed_at: string
  }
}

export type ShowcaseTestCase = {
  id: string
  category: string
  language: string
  query: string
  is_answerable: boolean
  target_docs: string[]
  retrieval_hit: boolean
  citation_correct: boolean
  grounding_valid: boolean
  passed: boolean
  failure_reason: string | null
  ground_truth_summary: string
}

export type ShowcaseEvaluationResponse = {
  evaluation_version: string
  dataset_version: string
  executed_at: string
  model: string
  embedding_model: string
  grounding_model: string
  metrics: {
    total_cases: number
    passed: number
    failed: number
    pass_rate: number
    retrieval_hit_at_10: number
    citation_correctness: number
    grounding_validity: number
    unanswerable_rejection_rate: number
    persian_pass_rate: number
    english_pass_rate: number
    mixed_pass_rate: number
  }
  category_breakdown: Record<
    string,
    {
      total: number
      passed: number
      pass_rate: number
    }
  >
  cases: ShowcaseTestCase[]
}

export const FALLBACK_OVERVIEW: ShowcaseOverviewResponse = {
  status: 'System Ready',
  total_documents: 4,
  total_chunks: 12,
  indexed_at: '2026-09-22T13:48:40.000Z',
  documents: [
    {
      id: 'doc-01',
      filename: '01_annual_report_fa.pdf',
      title: 'گزارش عملکرد سالانه ۱۴۰۴',
      source_format: 'pdf',
      language: 'fa',
      pages_count: 3,
      chunks_count: 5,
      is_indexed: true,
      summary: 'تحلیل عملکرد مالی و عملیاتی شرکت، بررسی علل کاهش سود عملیاتی، و صورت‌های سود و زیان سالانه.',
      file_path: 'data/showcase_corpus/01_annual_report_fa.pdf',
      ingested_at: '2026-09-22T13:48:40.000Z',
    },
    {
      id: 'doc-02',
      filename: '02_financial_summary_en.pdf',
      title: 'Alborz Pioneer Tech - Financial Summary 2025',
      source_format: 'pdf',
      language: 'en',
      pages_count: 2,
      chunks_count: 3,
      is_indexed: true,
      summary: 'Annual financial summary in English covering statements of operations, segment revenue, and capital expenditure.',
      file_path: 'data/showcase_corpus/02_financial_summary_en.pdf',
      ingested_at: '2026-09-22T13:48:40.000Z',
    },
    {
      id: 'doc-03',
      filename: '03_strategy_mixed.pdf',
      title: 'گزارش استراتژی و تحول دیجیتال — Strategy & Digital Transformation 2025-2026',
      source_format: 'pdf',
      language: 'mixed',
      pages_count: 2,
      chunks_count: 2,
      is_indexed: true,
      summary: 'سند استراتژی تحول دیجیتال و پیاده‌سازی سیستم‌های LLM، معماری ابری و شاخص‌های کلیدی SLA.',
      file_path: 'data/showcase_corpus/03_strategy_mixed.pdf',
      ingested_at: '2026-09-22T13:48:40.000Z',
    },
    {
      id: 'doc-04',
      filename: '04_hr_performance_fa.pdf',
      title: 'گزارش عملکرد منابع انسانی و سرمایه سازمانی ۱۴۰۴',
      source_format: 'pdf',
      language: 'fa',
      pages_count: 2,
      chunks_count: 2,
      is_indexed: true,
      summary: 'گزارش سرمایه انسانی، توزیع نیروهای فنی، نرخ نگه‌داشت ۸۹ درصدی متخصصان و شاخص‌های بهره‌وری.',
      file_path: 'data/showcase_corpus/04_hr_performance_fa.pdf',
      ingested_at: '2026-09-22T13:48:40.000Z',
    },
  ],
}

export const FALLBACK_ANALYSIS: ShowcaseAnalysisResponse = {
  question: 'بر اساس گزارش عملکرد سال ۱۴۰۴، مهم‌ترین عوامل کاهش سود عملیاتی شرکت چه بوده است؟',
  answer:
    'بر اساس گزارش عملکرد سال ۱۴۰۴ شرکت فناوری پیشگامان البرز، با وجود رشد ۲۴ درصدی درآمد کل و رسیدن آن به مبلغ ۱۸۵ میلیارد تومان، سود عملیاتی شرکت با ۲۶ درصد کاهش از ۴۲ میلیارد تومان در سال قبل به ۳۱ میلیارد تومان رسیده و حاشیه سود عملیاتی از ۲۸.۲ درصد به ۱۶.۷ درصد افت کرده است [1].\n\nمهم‌ترین عوامل مؤثر بر این کاهش سود عملیاتی بر پایه گزارش به شرح زیر است:\n\n۱. **افزایش ۲۸ درصدی هزینه‌های زیرساخت ابری:** به دلیل سرمایه‌گذاری سنگین در سرورهای پردازشی هوش مصنوعی و ارتقای پهنای باند اختصاصی [1][2].\n۲. **افزایش هزینه‌های جذب و نگه‌داشت نخبگان:** رقابت فشرده در بازار کار حوزه مهندسی نرم‌افزار و جبران خدمات تیم‌های فنی [1].\n۳. **نوسانات نرخ ارز:** اثر مستقیم بر بهای تمام‌شده خرید تجهیزات شبکه، سخت‌افزار و سرورهای ذخیره‌سازی داده [1].\n۴. **هزینه‌های سربار اداری و توسعه شعب:** راه‌اندازی و تجهیز دفاتر استانی در دو شهر مشهد و اصفهان [1].',
  citations: [
    {
      citation_index: 1,
      document_id: 'doc-01',
      document_title: 'گزارش عملکرد سالانه ۱۴۰۴',
      document_format: 'pdf',
      page: '1',
      chunk_id: 'chunk-01',
      chunk_index: 0,
      excerpt:
        'در سال مالی ۱۴۰۴، درآمد کل شرکت با رشد ۲۴ درصدی به مبلغ ۱۸۵ میلیارد تومان رسید. با این وجود، سود عملیاتی شرکت از ۴۲ میلیارد تومان در سال ۱۴۰۳ به ۳۱ میلیارد تومان کاهش یافت. حاشیه سود عملیاتی شرکت از ۲۸.۲ درصد به ۱۶.۷ درصد کاهش یافته است.\n\nمهم‌ترین عوامل کاهش سود عملیاتی در سال ۱۴۰۴ عبارتند از:\n۱. افزایش ۲۸ درصدی هزینه‌های زیرساخت ابری و سرورهای پردازشی هوش مصنوعی در طول سال.\n۲. افزایش هزینه‌های حقوق، دستمزد و جذب نخبگان حوزه نرم‌افزار به علت رقابت شدید بازار کار.\n۳. نوسانات شدید نرخ ارز که بهای تمام‌شده تجهیزات شبکه و ذخیره‌سازی را افزایش داده است.\n۴. افزایش هزینه‌های سربار اداری و توسعه شعب استانی در دو شهر مشهد و اصفهان.',
      role: 'anchor',
    },
    {
      citation_index: 2,
      document_id: 'doc-01',
      document_title: 'گزارش عملکرد سالانه ۱۴۰۴',
      document_format: 'pdf',
      page: '2',
      chunk_id: 'chunk-02',
      chunk_index: 1,
      excerpt:
        'بخش خدمات ابری و زیرساخت داده (Cloud & Data Services):\nدرآمد این بخش با ۳۵ درصد رشد به ۱۱۰ میلیارد تومان رسید که ۵۹ درصد کل درآمد شرکت را تشکیل می‌دهد. به دلیل ارتقای پهنای باند و سرمایه‌گذاری سنگین در امنیت شبکه، حاشیه سود این بخش از ۳۳٪ به ۲۱٪ کاهش یافت.',
      role: 'anchor',
    },
  ],
  analysis_trace: [
    {
      step: 'Query normalized',
      status: 'completed',
      label: 'نرمال‌سازی پرسمان',
      detail: 'اعمال پاک‌سازی ZWNJ، استانداردسازی حروف فارسی/عربی و ارقام',
      elapsed_ms: 14,
    },
    {
      step: 'Semantic retrieval',
      status: 'completed',
      label: 'بازیابی معنایی',
      detail: 'استخراج بردار پرسمان با text-embedding-3-small و جستجوی شباهت کسینوسی',
      elapsed_ms: 68,
    },
    {
      step: 'Keyword retrieval',
      status: 'completed',
      label: 'بازیابی کلیدواژه‌ای',
      detail: 'جستجوی واژگانی مبتنی بر نمایه PostgreSQL Full-Text Search و عبارات فارسی',
      elapsed_ms: 32,
    },
    {
      step: 'RRF fusion',
      status: 'completed',
      label: 'ترکیب RRF',
      detail: 'ادغام رتبه‌بندی نتایج معنایی و متنی با ضریب k=60',
      elapsed_ms: 8,
    },
    {
      step: 'Context assembled',
      status: 'completed',
      label: 'گردآوری بافت منبع',
      detail: 'انتخاب ۵ گذرواژه با بالاترین امتیاز همراه با حریم بندهای همسایه',
      elapsed_ms: 19,
    },
    {
      step: 'Answer generated',
      status: 'completed',
      label: 'تولید پاسخ مستند',
      detail: 'اجرای عامل هوشمند با مدل gpt-5.5 و درج نشانگرهای استناد',
      elapsed_ms: 840,
    },
    {
      step: 'Grounding validated',
      status: 'completed',
      label: 'اعتبارسنجی استنادها',
      detail: 'تطبیق ادعاهای پاسخ با متن اصلی بندهای استخراج‌شده (Fail-Closed)',
      elapsed_ms: 115,
    },
    {
      step: 'Citations verified',
      status: 'completed',
      label: 'تأیید نهایی مراجع',
      detail: 'بررسی شناسه گذرواژه‌ها در پایگاه داده و استخراج گزیده از متن رسمی document_chunks.text',
      elapsed_ms: 22,
    },
  ],
  model_info: {
    llm_model: 'gpt-5.5',
    embedding_model: 'text-embedding-3-small',
    grounding_model: 'gpt-4.1-mini',
    executed_at: '2026-09-22T13:48:40.000Z',
  },
}

export const FALLBACK_EVALUATION: ShowcaseEvaluationResponse = {
  evaluation_version: '1.0.0',
  dataset_version: '1.0.0',
  executed_at: '2026-09-22T13:49:40.603Z',
  model: 'gpt-5.5',
  embedding_model: 'text-embedding-3-small',
  grounding_model: 'gpt-4.1-mini',
  metrics: {
    total_cases: 30,
    passed: 26,
    failed: 4,
    pass_rate: 86.7,
    retrieval_hit_at_10: 100.0,
    citation_correctness: 84.6,
    grounding_validity: 86.7,
    unanswerable_rejection_rate: 100.0,
    persian_pass_rate: 88.2,
    english_pass_rate: 100.0,
    mixed_pass_rate: 71.4,
  },
  category_breakdown: {
    persian_factual: { total: 8, passed: 6, pass_rate: 75.0 },
    english_factual: { total: 5, passed: 5, pass_rate: 100.0 },
    mixed_language: { total: 5, passed: 4, pass_rate: 80.0 },
    multi_document: { total: 5, passed: 4, pass_rate: 80.0 },
    multi_chunk_reasoning: { total: 3, passed: 3, pass_rate: 100.0 },
    unanswerable: { total: 4, passed: 4, pass_rate: 100.0 },
  },
  cases: [
    {
      id: 'EVAL-001',
      category: 'persian_factual',
      language: 'fa',
      query: 'در سال مالی ۱۴۰۴ درآمد کل شرکت چقدر بوده است؟',
      is_answerable: true,
      target_docs: ['01_annual_report_fa.pdf'],
      retrieval_hit: true,
      citation_correct: false,
      grounding_valid: false,
      passed: false,
      failure_reason: "Missing required evidence keywords in top passages: ['۱۸۵', '۱۴۰۴']",
      ground_truth_summary: 'درآمد کل شرکت با رشد ۲۴ درصدی به مبلغ ۱۸۵ میلیارد تومان رسید.',
    },
    {
      id: 'EVAL-002',
      category: 'persian_factual',
      language: 'fa',
      query: 'بر اساس گزارش عملکرد سال ۱۴۰۴، مهم‌ترین عوامل کاهش سود عملیاتی شرکت چه بوده است؟',
      is_answerable: true,
      target_docs: ['01_annual_report_fa.pdf'],
      retrieval_hit: true,
      citation_correct: true,
      grounding_valid: true,
      passed: true,
      failure_reason: null,
      ground_truth_summary: 'افزایش ۲۸ درصدی هزینه‌های زیرساخت ابری، افزایش هزینه‌های جذب نخبگان و نوسانات نرخ ارز.',
    },
    {
      id: 'EVAL-003',
      category: 'persian_factual',
      language: 'fa',
      query: 'سود عملیاتی شرکت در سال ۱۴۰۴ در مقایسه با سال ۱۴۰۳ چه تغییری کرد؟',
      is_answerable: true,
      target_docs: ['01_annual_report_fa.pdf'],
      retrieval_hit: true,
      citation_correct: true,
      grounding_valid: true,
      passed: true,
      failure_reason: null,
      ground_truth_summary: 'سود عملیاتی از ۴۲ میلیارد تومان در سال ۱۴۰۳ به ۳۱ میلیارد تومان (۲۶ درصد کاهش) رسید.',
    },
    {
      id: 'EVAL-004',
      category: 'persian_factual',
      language: 'fa',
      query: 'حاشیه سود ناخالص شرکت در سال ۱۴۰۴ چند درصد گزارش شده است؟',
      is_answerable: true,
      target_docs: ['01_annual_report_fa.pdf'],
      retrieval_hit: true,
      citation_correct: true,
      grounding_valid: true,
      passed: true,
      failure_reason: null,
      ground_truth_summary: 'حاشیه سود ناخالص در سال ۱۴۰۴ برابر ۳۶.۲ درصد گزارش شده است.',
    },
    {
      id: 'EVAL-005',
      category: 'persian_factual',
      language: 'fa',
      query: 'درآمد بخش خدمات ابری و پردازش داده شرکت چقدر بوده است؟',
      is_answerable: true,
      target_docs: ['01_annual_report_fa.pdf'],
      retrieval_hit: true,
      citation_correct: true,
      grounding_valid: true,
      passed: true,
      failure_reason: null,
      ground_truth_summary: 'درآمد بخش خدمات ابری با ۳۵ درصد رشد به ۱۱۰ میلیارد تومان رسید.',
    },
    {
      id: 'EVAL-006',
      category: 'persian_factual',
      language: 'fa',
      query: 'تعداد کل همکاران تمام‌وقت شرکت در پایان سال ۱۴۰۴ چند نفر بوده است؟',
      is_answerable: true,
      target_docs: ['04_hr_performance_fa.pdf'],
      retrieval_hit: true,
      citation_correct: true,
      grounding_valid: true,
      passed: true,
      failure_reason: null,
      ground_truth_summary: 'تعداد کل همکاران تمام‌وقت شرکت در پایان سال ۱۴۰۴ به ۴۸۰ نفر رسید.',
    },
    {
      id: 'EVAL-007',
      category: 'persian_factual',
      language: 'fa',
      query: 'چند درصد از نیروهای شرکت در بخش‌های فنی و مهندسی مشغول به کارند؟',
      is_answerable: true,
      target_docs: ['04_hr_performance_fa.pdf'],
      retrieval_hit: true,
      citation_correct: true,
      grounding_valid: true,
      passed: true,
      failure_reason: null,
      ground_truth_summary: '۶۲ درصد پرسنل در بخش‌های فنی، مهندسی نرم‌افزار و هوش مصنوعی مشغولند.',
    },
    {
      id: 'EVAL-008',
      category: 'persian_factual',
      language: 'fa',
      query: 'نرخ نگه‌داشت نخبگان و نیروهای کلیدی شرکت در سال ۱۴۰۴ چقدر بوده است؟',
      is_answerable: true,
      target_docs: ['04_hr_performance_fa.pdf'],
      retrieval_hit: true,
      citation_correct: false,
      grounding_valid: false,
      passed: false,
      failure_reason: "Missing required evidence keywords in top passages: ['نگه‌داشت', '۸۹']",
      ground_truth_summary: 'نرخ نگه‌داشت متخصصان و نخبگان کلیدی شرکت ۸۹ درصد بوده است.',
    },
    {
      id: 'EVAL-009',
      category: 'english_factual',
      language: 'en',
      query: 'What was the total consolidated revenue of the company in fiscal year 2025?',
      is_answerable: true,
      target_docs: ['02_financial_summary_en.pdf'],
      retrieval_hit: true,
      citation_correct: true,
      grounding_valid: true,
      passed: true,
      failure_reason: null,
      ground_truth_summary: 'Total consolidated revenue was $42.5 million, up 24.3% YoY.',
    },
    {
      id: 'EVAL-010',
      category: 'english_factual',
      language: 'en',
      query: 'How much operating income was reported in 2025 compared to 2024?',
      is_answerable: true,
      target_docs: ['02_financial_summary_en.pdf'],
      retrieval_hit: true,
      citation_correct: true,
      grounding_valid: true,
      passed: true,
      failure_reason: null,
      ground_truth_summary: 'Operating income was $8.2 million in 2025 compared to $10.5 million in 2024.',
    },
    {
      id: 'EVAL-011',
      category: 'english_factual',
      language: 'en',
      query: 'What factors drove the reduction in operating margin in the financial summary?',
      is_answerable: true,
      target_docs: ['02_financial_summary_en.pdf'],
      retrieval_hit: true,
      citation_correct: true,
      grounding_valid: true,
      passed: true,
      failure_reason: null,
      ground_truth_summary: 'Elevated GPU computing cluster lease expenses and talent acquisition costs.',
    },
    {
      id: 'EVAL-012',
      category: 'english_factual',
      language: 'en',
      query: 'How much revenue did the Enterprise SaaS segment generate in 2025?',
      is_answerable: true,
      target_docs: ['02_financial_summary_en.pdf'],
      retrieval_hit: true,
      citation_correct: true,
      grounding_valid: true,
      passed: true,
      failure_reason: null,
      ground_truth_summary: 'Enterprise SaaS revenue reached $25.8 million, up 28.0% YoY.',
    },
    {
      id: 'EVAL-013',
      category: 'english_factual',
      language: 'en',
      query: 'What was the total capital expenditure in 2025 and what were the priority areas?',
      is_answerable: true,
      target_docs: ['02_financial_summary_en.pdf'],
      retrieval_hit: true,
      citation_correct: true,
      grounding_valid: true,
      passed: true,
      failure_reason: null,
      ground_truth_summary: 'CapEx was $5.4 million for GPU inference servers, network interconnects, and SOC 2 audits.',
    },
    {
      id: 'EVAL-014',
      category: 'mixed_language',
      language: 'mixed',
      query: 'معماری فناوری و سیستم‌های شرکت بر چه پلتفرم‌ها و دیتابیس‌هایی استوار است؟',
      is_answerable: true,
      target_docs: ['03_strategy_mixed.pdf'],
      retrieval_hit: true,
      citation_correct: true,
      grounding_valid: true,
      passed: true,
      failure_reason: null,
      ground_truth_summary: 'معماری Cloud Native مبتنی بر Supabase و PostgreSQL با جستجوی ترکیبی RRF و pgvector.',
    },
    {
      id: 'EVAL-015',
      category: 'mixed_language',
      language: 'mixed',
      query: 'پایداری سرویس و توافق‌نامه سطح خدمات (Uptime SLA) شرکت چند درصد تضمین شده است؟',
      is_answerable: true,
      target_docs: ['03_strategy_mixed.pdf'],
      retrieval_hit: true,
      citation_correct: true,
      grounding_valid: true,
      passed: true,
      failure_reason: null,
      ground_truth_summary: 'پایداری و دسترسی‌پذیری سیستم (Uptime SLA) به میزان ۹۹.۹۵ درصد تضمین شده است.',
    },
    {
      id: 'EVAL-016',
      category: 'mixed_language',
      language: 'mixed',
      query: 'میانگین زمان پاسخگویی P95 Latency برای جستجوهای متنی و معنایی در سیستم چقدر هدف‌گذاری شده است؟',
      is_answerable: true,
      target_docs: ['03_strategy_mixed.pdf'],
      retrieval_hit: true,
      citation_correct: false,
      grounding_valid: false,
      passed: false,
      failure_reason: "Missing required evidence keywords in top passages: ['۳۵۰', 'میلی‌ثانیه']",
      ground_truth_summary: 'میانگین زمان پاسخگویی P95 زیر ۳۵۰ میلی‌ثانیه تثبیت می‌شود.',
    },
    {
      id: 'EVAL-017',
      category: 'mixed_language',
      language: 'mixed',
      query: 'تعداد مشتریان بخش Enterprise Solutions تا پایان سال ۲۰۲۶ چند سازمان هدف‌گذاری شده است؟',
      is_answerable: true,
      target_docs: ['03_strategy_mixed.pdf'],
      retrieval_hit: true,
      citation_correct: true,
      grounding_valid: true,
      passed: true,
      failure_reason: null,
      ground_truth_summary: 'افزایش مشتریان سازمانی فعال به بیش از ۱۲۰ سازمان دولتی و خصوصی.',
    },
    {
      id: 'EVAL-018',
      category: 'mixed_language',
      language: 'mixed',
      query: 'استقرار سامانه Document Copilot چه اثری بر سرعت پاسخگویی به تحلیل‌های اسناد داشته است؟',
      is_answerable: true,
      target_docs: ['03_strategy_mixed.pdf'],
      retrieval_hit: true,
      citation_correct: true,
      grounding_valid: true,
      passed: true,
      failure_reason: null,
      ground_truth_summary: 'نرخ پاسخگویی به درخواست‌های تحلیلی را ۳ برابر سریع‌تر کرده است.',
    },
    {
      id: 'EVAL-019',
      category: 'multi_document',
      language: 'mixed',
      query: 'درآمد بخش راهکارهای سازمانی در گزارش سالانه فارسی و گزارش مالی انگلیسی چگونه گزارش شده است؟',
      is_answerable: true,
      target_docs: ['01_annual_report_fa.pdf', '02_financial_summary_en.pdf'],
      retrieval_hit: true,
      citation_correct: false,
      grounding_valid: false,
      passed: false,
      failure_reason: "Missing required evidence keywords in top passages: ['۷۵', '25.8', 'million']",
      ground_truth_summary: '۷۵ میلیارد تومان در گزارش فارسی و $25.8M در بخش Enterprise SaaS گزارش انگلیسی.',
    },
    {
      id: 'EVAL-020',
      category: 'multi_document',
      language: 'mixed',
      query: 'هزینه‌های کلاستر سرورهای ابری در گزارش مالی و برنامه زیرساخت در سند استراتژی چه ارتباطی دارند؟',
      is_answerable: true,
      target_docs: ['01_annual_report_fa.pdf', '03_strategy_mixed.pdf'],
      retrieval_hit: true,
      citation_correct: true,
      grounding_valid: true,
      passed: true,
      failure_reason: null,
      ground_truth_summary: 'مهار رشد ۲۸ درصدی هزینه‌های ابری از طریق استقرار معماری ترکیبی Hybrid Cloud و دیتاسنتر پیام.',
    },
    {
      id: 'EVAL-021',
      category: 'multi_document',
      language: 'fa',
      query: 'نرخ تمدید قراردادهای مشتریان و برنامه گسترش بازار سازمانی در اسناد شرکت چگونه منعکس شده است؟',
      is_answerable: true,
      target_docs: ['01_annual_report_fa.pdf', '03_strategy_mixed.pdf'],
      retrieval_hit: true,
      citation_correct: true,
      grounding_valid: true,
      passed: true,
      failure_reason: null,
      ground_truth_summary: 'نرخ تمدید ۹۴ درصدی مشتریان و ارتقای سازمان‌های هدف به ۱۲۰ مشتری تا پایان ۲۰۲۶.',
    },
    {
      id: 'EVAL-022',
      category: 'multi_document',
      language: 'fa',
      query: 'افزایش هزینه‌های جذب متخصصان در گزارش مالی و تعداد پرسنل فنی در گزارش منابع انسانی چه نسبتی دارند؟',
      is_answerable: true,
      target_docs: ['01_annual_report_fa.pdf', '04_hr_performance_fa.pdf'],
      retrieval_hit: true,
      citation_correct: true,
      grounding_valid: true,
      passed: true,
      failure_reason: null,
      ground_truth_summary: 'افزایش هزینه حقوق نیروهای فنی به عنوان عامل افت سود؛ ۴۸۰ نفر پرسنل با سهم ۶۲ درصدی فنی.',
    },
    {
      id: 'EVAL-023',
      category: 'multi_document',
      language: 'fa',
      query: 'سرمایه‌گذاری بر آموزش هوش مصنوعی در گزارش منابع انسانی و توسعه مدل‌های زبانی در سند استراتژی چیست؟',
      is_answerable: true,
      target_docs: ['03_strategy_mixed.pdf', '04_hr_performance_fa.pdf'],
      retrieval_hit: true,
      citation_correct: true,
      grounding_valid: true,
      passed: true,
      failure_reason: null,
      ground_truth_summary: 'برگزاری ۱۲,۴۰۰ نفر-ساعت آموزش هوش مصنوعی برای پشتیبانی از توسعه Document Copilot و LLMها.',
    },
    {
      id: 'EVAL-024',
      category: 'multi_chunk_reasoning',
      language: 'fa',
      query: 'چرا با وجود رشد ۲۴ درصدی درآمد کل شرکت، سود عملیاتی سال ۱۴۰۴ با افت ۲۶ درصدی مواجه شد؟',
      is_answerable: true,
      target_docs: ['01_annual_report_fa.pdf'],
      retrieval_hit: true,
      citation_correct: true,
      grounding_valid: true,
      passed: true,
      failure_reason: null,
      ground_truth_summary: 'افزایش ۲۸ درصدی هزینه‌های پردازش ابری، افزایش حقوق متخصصان، نوسان ارز و توسعه شعب مشهد و اصفهان.',
    },
    {
      id: 'EVAL-025',
      category: 'multi_chunk_reasoning',
      language: 'fa',
      query: 'برنامه شرکت برای بازگرداندن حاشیه سود عملیاتی به بالای ۲۲ درصد در سال ۱۴۰۵ شامل چه مراحلی است؟',
      is_answerable: true,
      target_docs: ['01_annual_report_fa.pdf'],
      retrieval_hit: true,
      citation_correct: true,
      grounding_valid: true,
      passed: true,
      failure_reason: null,
      ground_truth_summary: 'مهاجرت به معماری ترکیبی و بهره‌برداری از مرکز داده اختصاصی پیام با ۲۰ میلیارد تومان صرفه‌جویی.',
    },
    {
      id: 'EVAL-026',
      category: 'multi_chunk_reasoning',
      language: 'fa',
      query: 'تأثیر مدل اشتراک سالانه (SaaS) بر پایداری جریان درآمدی و توزیع نیروهای فنی شرکت چیست؟',
      is_answerable: true,
      target_docs: ['01_annual_report_fa.pdf', '04_hr_performance_fa.pdf'],
      retrieval_hit: true,
      citation_correct: true,
      grounding_valid: true,
      passed: true,
      failure_reason: null,
      ground_truth_summary: 'سهم ۶۰ درصدی مدل SaaS، نرخ تمدید ۹۴ درصدی، و تخصیص ۶۲ درصد پرسنل به تیم‌های مهندسی و هوش مصنوعی.',
    },
    {
      id: 'EVAL-027',
      category: 'unanswerable',
      language: 'fa',
      query: 'سود خالص شرکت پس از کسر مالیات در سال ۱۴۰۴ دقیقاً چقدر بوده است؟',
      is_answerable: false,
      target_docs: ['01_annual_report_fa.pdf'],
      retrieval_hit: true,
      citation_correct: true,
      grounding_valid: true,
      passed: true,
      failure_reason: null,
      ground_truth_summary: 'اطلاعات سود خالص پس از مالیات در اسناد موجود نیست (فقط سود ناخالص و عملیاتی ذکر شده).',
    },
    {
      id: 'EVAL-028',
      category: 'unanswerable',
      language: 'fa',
      query: 'آدرس دقیق شعبه شرکت در کشور امارات و دبی چیست؟',
      is_answerable: false,
      target_docs: [],
      retrieval_hit: true,
      citation_correct: true,
      grounding_valid: true,
      passed: true,
      failure_reason: null,
      ground_truth_summary: 'شرکت فاقد شعبه در امارات است (تنها شعب مشهد و اصفهان در اسناد ذکر شده‌اند).',
    },
    {
      id: 'EVAL-029',
      category: 'unanswerable',
      language: 'en',
      query: 'What was the total dividend per share distributed to common shareholders in 2025?',
      is_answerable: false,
      target_docs: ['02_financial_summary_en.pdf'],
      retrieval_hit: true,
      citation_correct: true,
      grounding_valid: true,
      passed: true,
      failure_reason: null,
      ground_truth_summary: 'No dividend per share information is contained in the financial summary.',
    },
    {
      id: 'EVAL-030',
      category: 'unanswerable',
      language: 'fa',
      query: 'شرکت از چه مدل کوانتومی برای رمزنگاری تراکنش‌های بانکی خود استفاده می‌کند؟',
      is_answerable: false,
      target_docs: [],
      retrieval_hit: true,
      citation_correct: true,
      grounding_valid: true,
      passed: true,
      failure_reason: null,
      ground_truth_summary: 'ادعای ساختگی خارج از دامنه؛ هیچ‌گونه فناوری کوانتومی در اسناد ذکر نشده است.',
    },
  ],
}

export async function fetchShowcaseOverview(): Promise<ShowcaseOverviewResponse> {
  try {
    const res = await fetch(`${env.apiBaseUrl}/showcase/overview`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return (await res.json()) as ShowcaseOverviewResponse
  } catch {
    return FALLBACK_OVERVIEW
  }
}

export async function fetchShowcaseAnalysis(): Promise<ShowcaseAnalysisResponse> {
  try {
    const res = await fetch(`${env.apiBaseUrl}/showcase/analysis`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return (await res.json()) as ShowcaseAnalysisResponse
  } catch {
    return FALLBACK_ANALYSIS
  }
}

export async function fetchShowcaseEvaluation(): Promise<ShowcaseEvaluationResponse> {
  try {
    const res = await fetch(`${env.apiBaseUrl}/showcase/evaluation`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return (await res.json()) as ShowcaseEvaluationResponse
  } catch {
    return FALLBACK_EVALUATION
  }
}
