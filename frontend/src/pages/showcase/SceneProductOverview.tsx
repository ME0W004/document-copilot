import { useEffect, useState } from 'react'
import { FileText, CheckCircle2, Layers, Cpu, Database, Search } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { fetchShowcaseOverview, type ShowcaseOverviewResponse } from '@/lib/showcase'

export function SceneProductOverview() {
  const [data, setData] = useState<ShowcaseOverviewResponse | null>(null)

  useEffect(() => {
    void fetchShowcaseOverview().then(setData)
  }, [])

  if (!data) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-sm text-muted-foreground">در حال بارگذاری اطلاعات اسناد...</p>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Header section */}
      <div className="flex flex-col gap-4 border-b border-border pb-6 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
              Document Copilot
            </h1>
            <span className="text-xl font-medium text-muted-foreground">|</span>
            <span className="text-lg font-medium text-muted-foreground">
              تحلیل هوشمند اسناد
            </span>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            محیط تحلیل سازمانی، بازیابی ترکیبی و استخراج گزاره‌های مستند از گزارش‌های مالی و راهبردی
          </p>
        </div>

        {/* System ready badge */}
        <div className="flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3.5 py-1.5 text-xs font-semibold text-emerald-600">
          <span className="size-2 rounded-full bg-emerald-500 animate-pulse" />
          <span>System Ready</span>
        </div>
      </div>

      {/* Document catalog grid */}
      <div>
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-foreground">
              اسناد فعال در مخزن دانش (Indexed Documents)
            </h2>
            <p className="text-xs text-muted-foreground">
              اسناد سنتتیک و استاندارد جهت آزمون بازیابی، خلاصه‌سازی و اعتبارسنجی استنادها
            </p>
          </div>
          <Badge variant="outline" className="text-xs font-normal">
            {data.total_documents} سند · {data.total_chunks} بند نمایه شده
          </Badge>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {data.documents.map((doc) => (
            <Card key={doc.id} className="border-border bg-card shadow-xs transition-colors hover:border-primary/30">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5 rounded-lg border border-border bg-muted/30 p-2 text-foreground">
                      <FileText className="size-5 text-muted-foreground" />
                    </div>
                    <div>
                      <CardTitle className="text-base leading-snug font-semibold text-foreground">
                        {doc.title}
                      </CardTitle>
                      <CardDescription className="mt-1 font-mono text-xs text-muted-foreground">
                        {doc.filename}
                      </CardDescription>
                    </div>
                  </div>
                  <Badge variant="secondary" className="font-mono text-[0.7rem] uppercase">
                    {doc.source_format}
                  </Badge>
                </div>
              </CardHeader>

              <CardContent className="space-y-4">
                <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                  {doc.summary}
                </p>

                <div className="flex flex-wrap items-center justify-between border-t border-border/60 pt-3 text-xs">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="font-mono text-[0.7rem] uppercase">
                      {doc.language}
                    </Badge>
                    <span className="text-muted-foreground">·</span>
                    <span className="text-muted-foreground">{doc.pages_count} صفحه</span>
                    <span className="text-muted-foreground">·</span>
                    <span className="text-muted-foreground">{doc.chunks_count} بند (chunks)</span>
                  </div>

                  <div className="flex items-center gap-1.5 font-medium text-emerald-600">
                    <CheckCircle2 className="size-3.5" />
                    <span className="text-xs">Indexed ✓</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Technical Architecture Specs */}
      <Card className="border-border bg-muted/10 shadow-xs">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold text-foreground">
            مشخصات معماری پردازش و نمایه اسناد (Technical Architecture)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="flex items-start gap-3 rounded-lg border border-border bg-card p-3">
              <Database className="mt-0.5 size-4 text-muted-foreground shrink-0" />
              <div>
                <span className="block text-xs font-semibold text-foreground">
                  ذخیره‌سازی و نمایه
                </span>
                <span className="font-mono text-[0.75rem] text-muted-foreground">
                  Supabase Postgres + pgvector
                </span>
              </div>
            </div>

            <div className="flex items-start gap-3 rounded-lg border border-border bg-card p-3">
              <Search className="mt-0.5 size-4 text-muted-foreground shrink-0" />
              <div>
                <span className="block text-xs font-semibold text-foreground">
                  الگوریتم بازیابی ترکیبی
                </span>
                <span className="font-mono text-[0.75rem] text-muted-foreground">
                  Hybrid Search + RRF Fusion
                </span>
              </div>
            </div>

            <div className="flex items-start gap-3 rounded-lg border border-border bg-card p-3">
              <Layers className="mt-0.5 size-4 text-muted-foreground shrink-0" />
              <div>
                <span className="block text-xs font-semibold text-foreground">
                  جداسازی و بندبندی
                </span>
                <span className="font-mono text-[0.75rem] text-muted-foreground">
                  Docling HybridChunker (512 t)
                </span>
              </div>
            </div>

            <div className="flex items-start gap-3 rounded-lg border border-border bg-card p-3">
              <Cpu className="mt-0.5 size-4 text-muted-foreground shrink-0" />
              <div>
                <span className="block text-xs font-semibold text-foreground">
                  اعتبارسنجی استنادها
                </span>
                <span className="font-mono text-[0.75rem] text-muted-foreground">
                  Fail-Closed Grounding
                </span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
