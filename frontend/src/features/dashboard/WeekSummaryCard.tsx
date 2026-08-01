import { Clock, Target } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import type { ProgressSummary } from '@/types/study'

export function WeekSummaryCard({ progress }: { progress: ProgressSummary }) {
  return (
    <Card>
      <h2 className="mb-4 text-sm font-semibold text-ink-900">Resumen de esta semana</h2>
      <dl className="grid grid-cols-2 gap-4">
        <div className="flex items-start gap-2.5">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
            <Clock className="h-4.5 w-4.5" aria-hidden="true" />
          </span>
          <div>
            <dt className="text-xs text-ink-500">Minutos estudiados</dt>
            <dd className="text-lg font-semibold text-ink-900">{progress.weeklyMinutesStudied}</dd>
          </div>
        </div>
        <div className="flex items-start gap-2.5">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-positive-50 text-positive-600">
            <Target className="h-4.5 w-4.5" aria-hidden="true" />
          </span>
          <div>
            <dt className="text-xs text-ink-500">Temas comprendidos</dt>
            <dd className="text-lg font-semibold text-ink-900">
              {progress.topicsUnderstood}/{progress.topicsTotal}
            </dd>
          </div>
        </div>
      </dl>
    </Card>
  )
}
