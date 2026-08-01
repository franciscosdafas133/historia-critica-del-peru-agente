import { useEffect, useState } from 'react'
import { History, Lightbulb, Compass, Dumbbell, ClipboardCheck, RotateCcw, Swords } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { progressService } from '@/services/progressService'
import { APP_CONFIG } from '@/config/app.config'
import type { ActivityEntry, StudyMode } from '@/types/study'

const MODE_LABELS: Record<StudyMode, string> = {
  understand: 'Entender',
  solve: 'Resolver',
  practice: 'Practicar',
  assess: 'Evaluarme',
  review: 'Repasar',
  debate: 'Debatir',
}

const MODE_ICONS: Record<StudyMode, LucideIcon> = {
  understand: Lightbulb,
  solve: Compass,
  practice: Dumbbell,
  assess: ClipboardCheck,
  review: RotateCcw,
  debate: Swords,
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('es-PE', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

export function HistoryPage() {
  const [activity, setActivity] = useState<ActivityEntry[]>([])

  useEffect(() => {
    document.title = `Historial · ${APP_CONFIG.productName}`
    setActivity(progressService.getRecentActivity())
  }, [])

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-6 md:px-8 md:py-8">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-semibold text-ink-900">
          <History className="h-5 w-5 text-ink-500" aria-hidden="true" /> Historial de estudio
        </h1>
        <p className="mt-1 text-sm text-ink-500">Tus últimas sesiones registradas en este dispositivo.</p>
      </div>

      {activity.length === 0 ? (
        <Card>
          <p className="text-sm text-ink-500">
            Aún no tienes actividad. Empieza en la Sala de Estudio para ver tu historial aquí.
          </p>
        </Card>
      ) : (
        <ol className="space-y-3">
          {activity.map((entry) => {
            const Icon = MODE_ICONS[entry.mode]
            return (
              <li key={entry.id}>
                <Card className="flex items-start gap-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
                    <Icon className="h-4.5 w-4.5" aria-hidden="true" />
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm text-ink-900">{entry.summary}</p>
                    <p className="mt-0.5 text-xs text-ink-500">
                      Modo {MODE_LABELS[entry.mode]} · {formatDate(entry.timestamp)}
                    </p>
                  </div>
                </Card>
              </li>
            )
          })}
        </ol>
      )}
    </div>
  )
}
