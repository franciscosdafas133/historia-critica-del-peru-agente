import { History, Lightbulb, Compass, Dumbbell, ClipboardCheck, RotateCcw, Swords } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import type { ActivityEntry, StudyMode } from '@/types/study'

const MODE_ICONS: Record<StudyMode, LucideIcon> = {
  understand: Lightbulb,
  solve: Compass,
  practice: Dumbbell,
  assess: ClipboardCheck,
  review: RotateCcw,
  debate: Swords,
}

function formatRelativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diffMs / 60000)
  if (minutes < 1) return 'hace un momento'
  if (minutes < 60) return `hace ${minutes} min`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `hace ${hours} h`
  return `hace ${Math.floor(hours / 24)} d`
}

export function RecentActivityCard({ activity }: { activity: ActivityEntry[] }) {
  return (
    <Card>
      <h2 className="mb-3 flex items-center gap-1.5 text-sm font-semibold text-ink-900">
        <History className="h-4 w-4 text-ink-500" aria-hidden="true" />
        Actividad reciente
      </h2>
      {activity.length === 0 ? (
        <p className="text-sm text-ink-500">Aún no tienes actividad registrada. Empieza una sesión de estudio.</p>
      ) : (
        <ul className="space-y-3">
          {activity.slice(0, 5).map((entry) => {
            const Icon = MODE_ICONS[entry.mode]
            return (
              <li key={entry.id} className="flex items-start gap-2.5">
                <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-surface-200 text-ink-500">
                  <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                </span>
                <div className="min-w-0">
                  <p className="truncate text-sm text-ink-700">{entry.summary}</p>
                  <p className="text-xs text-ink-300">{formatRelativeTime(entry.timestamp)}</p>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}
