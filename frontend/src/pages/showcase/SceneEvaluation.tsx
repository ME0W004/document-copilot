import { useEffect, useState } from 'react'
import { CheckCircle2, XCircle, BarChart3, Database, ShieldCheck } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import {
  fetchShowcaseEvaluation,
  type ShowcaseEvaluationResponse,
  type ShowcaseTestCase,
} from '@/lib/showcase'

export function SceneEvaluation() {
  const [data, setData] = useState<ShowcaseEvaluationResponse | null>(null)
  const [filterCategory, setFilterCategory] = useState<string>('all')

  useEffect(() => {
    void fetchShowcaseEvaluation().then(setData)
  }, [])

  if (!data) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-sm text-muted-foreground">در حال بارگذاری کارنامه ارزیابی...</p>
      </div>
    )
  }

  const { metrics } = data

  const filteredCases: ShowcaseTestCase[] =
    filterCategory === 'all'
      ? data.cases
      : data.cases.filter((c) => c.category === filterCategory)

  return (
    <div className="space-y-8">
      {/* Header with Title and Model Metadata */}
      <div className="flex flex-col gap-4 border-b border-border pb-6 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="font-mono text-2xl font-bold tracking-tight text-foreground sm:text-3xl uppercase">
              EVALUATION DASHBOARD
            </h1>
            <span className="text-xl font-medium text-muted-foreground">|</span>
            <span className="text-lg font-medium text-muted-foreground">
              ارزیابی ۳۰ آزمون معیار
            </span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            گزارش واقعی آزمون‌های بازیابی ترکیبی، دقت استنادها و رد ادعاهای بدون شواهد (Fail-Closed)
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          <Badge variant="outline" className="font-mono text-[0.7rem]">
            Model: {data.model}
          </Badge>
          <Badge variant="outline" className="font-mono text-[0.7rem]">
            Embeddings: {data.embedding_model}
          </Badge>
          <Badge variant="outline" className="font-mono text-[0.7rem]">
            v{data.evaluation_version}
          </Badge>
        </div>
      </div>

      {/* Hero Metric Cards (3 Key Big Numbers) */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card className="border-border bg-card shadow-xs">
          <CardHeader className="pb-2">
            <CardDescription className="font-mono text-xs font-semibold text-muted-foreground uppercase">
              TEST CASES
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline justify-between">
              <span className="text-4xl font-extrabold text-foreground tabular-nums">
                {metrics.total_cases}
              </span>
              <span className="text-xs text-muted-foreground">مجموع آزمون‌ها</span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border bg-card shadow-xs">
          <CardHeader className="pb-2">
            <CardDescription className="font-mono text-xs font-semibold text-muted-foreground uppercase">
              PASSED CASES
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline justify-between">
              <span className="text-4xl font-extrabold text-emerald-600 tabular-nums">
                {metrics.passed}
              </span>
              <span className="text-xs text-muted-foreground">
                موفق ({metrics.failed} ناموفق)
              </span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border bg-card shadow-xs">
          <CardHeader className="pb-2">
            <CardDescription className="font-mono text-xs font-semibold text-muted-foreground uppercase">
              PASS RATE
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline justify-between">
              <span className="text-4xl font-extrabold text-foreground tabular-nums">
                {metrics.pass_rate}%
              </span>
              <span className="text-xs text-muted-foreground">نرخ قبولی کل</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Core Quality Metrics Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="border-border bg-card shadow-xs">
          <CardContent className="pt-5">
            <div className="flex items-center justify-between">
              <div>
                <span className="font-mono text-xs text-muted-foreground uppercase">
                  RETRIEVAL
                </span>
                <span className="block text-2xl font-bold text-foreground tabular-nums mt-1">
                  {metrics.retrieval_hit_at_10}%
                </span>
                <span className="text-[0.7rem] text-muted-foreground">Hit@10 Score</span>
              </div>
              <Database className="size-6 text-muted-foreground/40" />
            </div>
          </CardContent>
        </Card>

        <Card className="border-border bg-card shadow-xs">
          <CardContent className="pt-5">
            <div className="flex items-center justify-between">
              <div>
                <span className="font-mono text-xs text-muted-foreground uppercase">
                  GROUNDING
                </span>
                <span className="block text-2xl font-bold text-foreground tabular-nums mt-1">
                  {metrics.grounding_validity}%
                </span>
                <span className="text-[0.7rem] text-muted-foreground">Valid Evidence</span>
              </div>
              <ShieldCheck className="size-6 text-muted-foreground/40" />
            </div>
          </CardContent>
        </Card>

        <Card className="border-border bg-card shadow-xs">
          <CardContent className="pt-5">
            <div className="flex items-center justify-between">
              <div>
                <span className="font-mono text-xs text-muted-foreground uppercase">
                  CITATIONS
                </span>
                <span className="block text-2xl font-bold text-foreground tabular-nums mt-1">
                  {metrics.citation_correctness}%
                </span>
                <span className="text-[0.7rem] text-muted-foreground">Correct Provenance</span>
              </div>
              <BarChart3 className="size-6 text-muted-foreground/40" />
            </div>
          </CardContent>
        </Card>

        <Card className="border-border bg-card shadow-xs">
          <CardContent className="pt-5">
            <div className="flex items-center justify-between">
              <div>
                <span className="font-mono text-xs text-muted-foreground uppercase">
                  UNANSWERABLE
                </span>
                <span className="block text-2xl font-bold text-foreground tabular-nums mt-1">
                  {metrics.unanswerable_rejection_rate}%
                </span>
                <span className="text-[0.7rem] text-muted-foreground">Fail-Closed Handling</span>
              </div>
              <CheckCircle2 className="size-6 text-emerald-600/40" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Category Breakdown Chips */}
      <div className="rounded-xl border border-border bg-muted/20 p-4">
        <div className="mb-3 flex items-center justify-between">
          <span className="text-xs font-semibold text-foreground">
            تفکیک دسته‌بندی و نرخ موفقیت (Category Breakdown):
          </span>
          <span className="text-[0.7rem] text-muted-foreground">
            فارسی: {metrics.persian_pass_rate}% | انگلیسی: {metrics.english_pass_rate}% | ترکیبی: {metrics.mixed_pass_rate}%
          </span>
        </div>

        <div className="flex flex-wrap gap-2 text-xs">
          <button
            type="button"
            onClick={() => setFilterCategory('all')}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
              filterCategory === 'all'
                ? 'bg-primary text-primary-foreground'
                : 'bg-card border border-border text-muted-foreground hover:text-foreground'
            }`}
          >
            همه آزمون‌ها (۳۰)
          </button>

          {Object.entries(data.category_breakdown).map(([cat, info]) => (
            <button
              key={cat}
              type="button"
              onClick={() => setFilterCategory(cat)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                filterCategory === cat
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-card border border-border text-muted-foreground hover:text-foreground'
              }`}
            >
              {cat} ({info.passed}/{info.total} · {info.pass_rate}%)
            </button>
          ))}
        </div>
      </div>

      {/* Test Cases Detail Table */}
      <Card className="border-border bg-card shadow-xs">
        <CardHeader className="pb-3 border-b border-border/60">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base font-semibold text-foreground">
                جدول تفصیلی موارد ارزیابی (Evaluation Case Results)
              </CardTitle>
              <CardDescription className="text-xs text-muted-foreground mt-0.5">
                نمایش تمام موارد آزمون، وضعیت بازیابی، اعتبارسنجی استنادها و علت موارد ناموفق
              </CardDescription>
            </div>
            <span className="font-mono text-xs text-muted-foreground">
              {filteredCases.length} مورد نمایش داده شده
            </span>
          </div>
        </CardHeader>

        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-right text-xs">
              <thead className="bg-muted/30 text-muted-foreground border-b border-border font-medium">
                <tr>
                  <th className="py-2.5 px-3 font-mono">ID</th>
                  <th className="py-2.5 px-3">دسته‌بندی</th>
                  <th className="py-2.5 px-3">متن پرسمان (Query)</th>
                  <th className="py-2.5 px-2 text-center">Hit@10</th>
                  <th className="py-2.5 px-2 text-center">Grounding</th>
                  <th className="py-2.5 px-2 text-center">نتیجه</th>
                  <th className="py-2.5 px-3">توضیحات / علت عدم قبولی</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {filteredCases.map((c) => (
                  <tr key={c.id} className="hover:bg-muted/10 transition-colors">
                    <td className="py-2.5 px-3 font-mono font-semibold text-foreground">
                      {c.id}
                    </td>
                    <td className="py-2.5 px-3">
                      <Badge variant="outline" className="font-mono text-[0.65rem]">
                        {c.category}
                      </Badge>
                    </td>
                    <td className="py-2.5 px-3 max-w-xs truncate text-foreground font-medium" title={c.query}>
                      {c.query}
                    </td>
                    <td className="py-2.5 px-2 text-center font-mono">
                      {c.retrieval_hit ? (
                        <span className="text-emerald-600">✓</span>
                      ) : (
                        <span className="text-destructive">✗</span>
                      )}
                    </td>
                    <td className="py-2.5 px-2 text-center font-mono">
                      {c.grounding_valid ? (
                        <span className="text-emerald-600">✓</span>
                      ) : (
                        <span className="text-destructive">✗</span>
                      )}
                    </td>
                    <td className="py-2.5 px-2 text-center">
                      {c.passed ? (
                        <span className="inline-flex items-center gap-1 font-semibold text-emerald-600">
                          <CheckCircle2 className="size-3.5" />
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 font-semibold text-destructive">
                          <XCircle className="size-3.5" />
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-muted-foreground text-[0.7rem] max-w-sm">
                      {c.passed ? (
                        <span className="text-muted-foreground line-clamp-1">
                          {c.ground_truth_summary}
                        </span>
                      ) : (
                        <span className="text-destructive font-mono line-clamp-1">
                          {c.failure_reason}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
