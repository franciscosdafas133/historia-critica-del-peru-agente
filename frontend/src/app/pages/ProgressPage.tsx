import { useEffect, useState } from 'react'
import { TrendingUp, Trophy, RotateCcw } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { ProgressBar } from '@/components/ui/ProgressBar'
import { progressService } from '@/services/progressService'
import { PILOT_COURSE } from '@/mocks/courseData'
import { APP_CONFIG } from '@/config/app.config'
import type { AssessmentResult, ProgressSummary } from '@/types/study'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('es-PE', { day: 'numeric', month: 'long' })
}

export function ProgressPage() {
  const [progress, setProgress] = useState<ProgressSummary | null>(null)
  const [results, setResults] = useState<AssessmentResult[]>([])
  const [reviewFlags, setReviewFlags] = useState<string[]>([])

  useEffect(() => {
    document.title = `Progreso · ${APP_CONFIG.productName}`
    setProgress(progressService.getProgress())
    setResults(progressService.getAssessmentResults())
    setReviewFlags(progressService.getReviewFlags())
  }, [])

  if (!progress) return null

  const allTopics = PILOT_COURSE.units.flatMap((u) => u.weeks.flatMap((w) => w.topics))
  const flaggedTopics = allTopics.filter((t) => reviewFlags.includes(t.id))

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-6 md:px-8 md:py-8">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-semibold text-ink-900">
          <TrendingUp className="h-5 w-5 text-ink-500" aria-hidden="true" /> Tu progreso
        </h1>
        <p className="mt-1 text-sm text-ink-500">Historia Crítica del Perú — {PILOT_COURSE.professor}</p>
      </div>

      <Card>
        <ProgressBar percent={progress.overallPercent} label="Progreso general del curso" />
        <p className="mt-3 text-sm text-ink-500">
          {progress.topicsUnderstood} de {progress.topicsTotal} temas comprendidos · {progress.weeklyMinutesStudied} minutos
          estudiados esta semana
        </p>
      </Card>

      <Card>
        <h2 className="mb-3 flex items-center gap-1.5 text-sm font-semibold text-ink-900">
          <Trophy className="h-4 w-4 text-positive-500" aria-hidden="true" /> Resultados de evaluaciones
        </h2>
        {results.length === 0 ? (
          <p className="text-sm text-ink-500">Aún no completaste ninguna microevaluación.</p>
        ) : (
          <ul className="space-y-2.5">
            {results.map((result) => (
              <li key={result.id} className="flex items-center justify-between rounded-lg bg-surface-100 px-3.5 py-2.5">
                <span className="text-sm text-ink-700">{formatDate(result.completedAt)}</span>
                <span
                  className={`text-sm font-semibold ${result.score >= 60 ? 'text-positive-600' : 'text-attention-600'}`}
                >
                  {result.score}%
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <h2 className="mb-3 flex items-center gap-1.5 text-sm font-semibold text-ink-900">
          <RotateCcw className="h-4 w-4 text-attention-500" aria-hidden="true" /> Marcados para repaso
        </h2>
        {flaggedTopics.length === 0 ? (
          <p className="text-sm text-ink-500">No tienes temas pendientes de repaso.</p>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {flaggedTopics.map((topic) => (
              <li
                key={topic.id}
                className="rounded-full bg-attention-50 px-3 py-1 text-xs font-medium text-attention-700"
              >
                {topic.title}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
