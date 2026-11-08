import { useSearchParams } from 'react-router-dom'

import { SceneProductOverview } from '@/pages/showcase/SceneProductOverview'
import { SceneRealAnalysis } from '@/pages/showcase/SceneRealAnalysis'
import { SceneEvaluation } from '@/pages/showcase/SceneEvaluation'

type SceneType = 'product' | 'analysis' | 'evaluation'

export function ShowcasePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const currentScene = (searchParams.get('scene') as SceneType) || 'product'

  function setScene(scene: SceneType) {
    setSearchParams({ scene })
  }

  return (
    <div dir="rtl" className="min-h-screen bg-background text-foreground selection:bg-primary selection:text-primary-foreground">
      {/* Top Header & Navigation Bar */}
      <header className="sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
          <div className="flex items-center gap-4">
            <span className="font-mono text-xs font-black tracking-widest text-primary uppercase">
              SHOWCASE
            </span>
            <span className="h-4 w-px bg-border" />
            <nav className="flex items-center gap-1.5 sm:gap-2">
              <button
                type="button"
                onClick={() => setScene('product')}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                  currentScene === 'product'
                    ? 'bg-primary text-primary-foreground shadow-xs'
                    : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground'
                }`}
              >
                01 محصول
              </button>

              <button
                type="button"
                onClick={() => setScene('analysis')}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                  currentScene === 'analysis'
                    ? 'bg-primary text-primary-foreground shadow-xs'
                    : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground'
                }`}
              >
                02 تحلیل واقعی
              </button>

              <button
                type="button"
                onClick={() => setScene('evaluation')}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                  currentScene === 'evaluation'
                    ? 'bg-primary text-primary-foreground shadow-xs'
                    : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground'
                }`}
              >
                03 Evaluation
              </button>
            </nav>
          </div>

          <div className="hidden sm:flex items-center gap-2">
            <span className="font-mono text-[0.7rem] text-muted-foreground">
              Document Copilot Evidence Surface
            </span>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {currentScene === 'product' && <SceneProductOverview />}
        {currentScene === 'analysis' && <SceneRealAnalysis />}
        {currentScene === 'evaluation' && <SceneEvaluation />}
      </main>
    </div>
  )
}
