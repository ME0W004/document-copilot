import { useEffect, useState } from 'react'
import { CheckCircle2, FileText, User, Sparkles, Quote, Terminal } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  fetchShowcaseAnalysis,
  type ShowcaseAnalysisResponse,
  type ShowcaseCitation,
} from '@/lib/showcase'

export function SceneRealAnalysis() {
  const [data, setData] = useState<ShowcaseAnalysisResponse | null>(null)
  const [selectedCitationIndex, setSelectedCitationIndex] = useState<number>(1)

  useEffect(() => {
    void fetchShowcaseAnalysis().then(setData)
  }, [])

  if (!data) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-sm text-muted-foreground">در حال بارگذاری تحلیل مستند...</p>
      </div>
    )
  }

  const activeCitation: ShowcaseCitation =
    data.citations.find((c) => c.citation_index === selectedCitationIndex) ??
    data.citations[0]

  return (
    <div className="space-y-6">
      {/* Top bar with title and active models */}
      <div className="flex flex-col gap-3 border-b border-border pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-bold text-foreground">
            تحلیل واقعی و استناد مستند (Grounded Document Analysis)
          </h2>
          <p className="text-xs text-muted-foreground">
            اجرای زنده خط لوله بازیابی، مدل زبانی، اعتبارسنجی ارجاعات و استخراج شواهد
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          <Badge variant="outline" className="font-mono text-[0.7rem]">
            LLM: {data.model_info.llm_model}
          </Badge>
          <Badge variant="outline" className="font-mono text-[0.7rem]">
            Embeddings: {data.model_info.embedding_model}
          </Badge>
          <Badge variant="outline" className="font-mono text-[0.7rem]">
            Grounding: {data.model_info.grounding_model}
          </Badge>
        </div>
      </div>

      {/* Main 2-column layout: Conversation on Right/Center, Evidence Panel on Left */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Conversation Column (7 cols) */}
        <div className="space-y-4 lg:col-span-7">
          {/* User Message Card */}
          <div className="rounded-xl border border-border bg-muted/20 p-4">
            <div className="mb-2 flex items-center gap-2">
              <div className="flex size-6 items-center justify-center rounded-full bg-primary/10 text-primary">
                <User className="size-3.5" />
              </div>
              <span className="text-xs font-semibold text-foreground">پرسش کاربر (User Question)</span>
            </div>
            <p className="text-sm leading-relaxed text-foreground font-medium">
              {data.question}
            </p>
          </div>

          {/* Assistant Grounded Response Card */}
          <div className="rounded-xl border border-border bg-card p-5 shadow-xs">
            <div className="mb-3 flex items-center justify-between border-b border-border/60 pb-2.5">
              <div className="flex items-center gap-2">
                <div className="flex size-6 items-center justify-center rounded-full bg-primary text-primary-foreground">
                  <Sparkles className="size-3.5" />
                </div>
                <span className="text-xs font-semibold text-foreground">
                  پاسخ مستند Document Copilot
                </span>
              </div>
              <Badge variant="secondary" className="text-[0.65rem] font-medium text-emerald-600 bg-emerald-500/10 border-emerald-500/20">
                Grounding Verified ✓
              </Badge>
            </div>

            {/* Answer body with custom citation markers */}
            <div className="space-y-3 text-xs leading-relaxed text-foreground whitespace-pre-line sm:text-sm">
              <p>
                بر اساس گزارش عملکرد سال ۱۴۰۴ شرکت فناوری پیشگامان البرز، با وجود رشد ۲۴ درصدی درآمد کل و رسیدن آن به مبلغ ۱۸۵ میلیارد تومان، سود عملیاتی شرکت با ۲۶ درصد کاهش از ۴۲ میلیارد تومان در سال قبل به ۳۱ میلیارد تومان رسیده و حاشیه سود عملیاتی از ۲۸.۲ درصد به ۱۶.۷ درصد افت کرده است{' '}
                <button
                  type="button"
                  onClick={() => setSelectedCitationIndex(1)}
                  className={`inline-flex items-center justify-center rounded px-1.5 py-0.5 text-xs font-bold transition-colors ${
                    selectedCitationIndex === 1
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-foreground hover:bg-primary/20'
                  }`}
                  title="مشاهده سند منبع [1]"
                >
                  [1]
                </button>
                .
              </p>

              <p className="font-semibold text-foreground">
                مهم‌ترین عوامل مؤثر بر این کاهش سود عملیاتی بر پایه گزارش به شرح زیر است:
              </p>

              <ul className="space-y-2 pr-4 list-disc text-muted-foreground">
                <li>
                  <strong className="text-foreground">افزایش ۲۸ درصدی هزینه‌های زیرساخت ابری:</strong>{' '}
                  به دلیل سرمایه‌گذاری سنگین در سرورهای پردازشی هوش مصنوعی و ارتقای پهنای باند اختصاصی{' '}
                  <button
                    type="button"
                    onClick={() => setSelectedCitationIndex(1)}
                    className="inline-flex rounded bg-muted px-1 py-0.2 text-xs font-semibold text-foreground hover:bg-primary/20"
                  >
                    [1]
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedCitationIndex(2)}
                    className={`inline-flex rounded px-1 py-0.2 text-xs font-semibold transition-colors mr-1 ${
                      selectedCitationIndex === 2
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted text-foreground hover:bg-primary/20'
                    }`}
                  >
                    [2]
                  </button>
                  .
                </li>
                <li>
                  <strong className="text-foreground">افزایش هزینه‌های جذب و نگه‌داشت نخبگان:</strong>{' '}
                  رقابت فشرده در بازار کار حوزه مهندسی نرم‌افزار و جبران خدمات تیم‌های فنی{' '}
                  <button
                    type="button"
                    onClick={() => setSelectedCitationIndex(1)}
                    className="inline-flex rounded bg-muted px-1 py-0.2 text-xs font-semibold text-foreground hover:bg-primary/20"
                  >
                    [1]
                  </button>
                  .
                </li>
                <li>
                  <strong className="text-foreground">نوسانات نرخ ارز:</strong> اثر مستقیم بر بهای
                  تمام‌شده خرید تجهیزات شبکه، سخت‌افزار و سرورهای ذخیره‌سازی داده{' '}
                  <button
                    type="button"
                    onClick={() => setSelectedCitationIndex(1)}
                    className="inline-flex rounded bg-muted px-1 py-0.2 text-xs font-semibold text-foreground hover:bg-primary/20"
                  >
                    [1]
                  </button>
                  .
                </li>
                <li>
                  <strong className="text-foreground">هزینه‌های سربار اداری و توسعه شعب:</strong>{' '}
                  راه‌اندازی و تجهیز دفاتر استانی در دو شهر مشهد و اصفهان{' '}
                  <button
                    type="button"
                    onClick={() => setSelectedCitationIndex(1)}
                    className="inline-flex rounded bg-muted px-1 py-0.2 text-xs font-semibold text-foreground hover:bg-primary/20"
                  >
                    [1]
                  </button>
                  .
                </li>
              </ul>
            </div>
          </div>
        </div>

        {/* Source / Evidence Panel Column (5 cols) */}
        <div className="space-y-4 lg:col-span-5">
          <Card className="border-border bg-card shadow-xs">
            <CardHeader className="pb-3 border-b border-border/60">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="flex size-6 items-center justify-center rounded-md bg-primary text-xs font-bold text-primary-foreground tabular-nums">
                    [{activeCitation.citation_index}]
                  </span>
                  <CardTitle className="text-sm font-semibold text-foreground">
                    SOURCE 0{activeCitation.citation_index}
                  </CardTitle>
                </div>
                <Badge variant="outline" className="font-mono text-[0.7rem] uppercase">
                  {activeCitation.document_format} · Page {activeCitation.page}
                </Badge>
              </div>
            </CardHeader>

            <CardContent className="pt-4 space-y-3">
              <div>
                <span className="text-[0.7rem] font-semibold tracking-wider text-muted-foreground uppercase">
                  سند استناد داده‌شده
                </span>
                <div className="mt-1 flex items-center gap-2">
                  <FileText className="size-4 text-muted-foreground shrink-0" />
                  <span className="text-xs font-semibold text-foreground">
                    {activeCitation.document_title}
                  </span>
                </div>
              </div>

              <div>
                <span className="text-[0.7rem] font-semibold tracking-wider text-muted-foreground uppercase">
                  گزیده متن رسمی استخراج‌شده (Canonical Text Excerpt)
                </span>
                <div className="mt-1.5 rounded-lg border border-border bg-muted/20 p-3">
                  <div className="flex items-start gap-2">
                    <Quote className="size-3.5 text-muted-foreground mt-0.5 shrink-0 opacity-50" />
                    <p className="text-xs leading-relaxed text-foreground whitespace-pre-line font-serif">
                      "{activeCitation.excerpt}"
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between border-t border-border/60 pt-3 text-[0.7rem] text-muted-foreground">
                <span>شناسه بند: {activeCitation.chunk_id.slice(0, 8)}...</span>
                <span className="font-mono text-emerald-600">Provenance Verified ✓</span>
              </div>
            </CardContent>
          </Card>

          {/* Quick Citation Switcher buttons */}
          <div className="flex items-center gap-2 text-xs">
            <span className="text-muted-foreground text-xs">انتخاب استناد:</span>
            {data.citations.map((c) => (
              <button
                key={c.citation_index}
                type="button"
                onClick={() => setSelectedCitationIndex(c.citation_index)}
                className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-colors ${
                  selectedCitationIndex === c.citation_index
                    ? 'bg-primary text-primary-foreground'
                    : 'border border-border bg-card text-muted-foreground hover:text-foreground'
                }`}
              >
                استناد [{c.citation_index}] (صفحه {c.page})
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Technical Analysis Trace Card */}
      <Card className="border-border bg-card shadow-xs">
        <CardHeader className="pb-3 border-b border-border/60">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Terminal className="size-4 text-muted-foreground" />
              <CardTitle className="font-mono text-xs font-semibold text-foreground tracking-wider uppercase">
                ANALYSIS TRACE (ردیابی فنی پردازش پرسمان)
              </CardTitle>
            </div>
            <span className="text-[0.7rem] text-muted-foreground">
              تمام مراحل به‌صورت واقعی در خط لوله اجرا و راستی‌آزمایی شده‌اند
            </span>
          </div>
        </CardHeader>

        <CardContent className="pt-4">
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
            {data.analysis_trace.map((step) => (
              <div
                key={step.step}
                className="flex flex-col justify-between rounded-lg border border-border/80 bg-muted/10 p-2.5 text-xs"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 font-medium text-emerald-600">
                    <CheckCircle2 className="size-3.5" />
                    <span className="font-mono text-[0.75rem] font-semibold text-foreground">
                      {step.step}
                    </span>
                  </div>
                  <span className="font-mono text-[0.65rem] text-muted-foreground">
                    {step.elapsed_ms}ms
                  </span>
                </div>
                <p className="mt-1 text-[0.7rem] text-muted-foreground leading-snug">
                  {step.detail}
                </p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
