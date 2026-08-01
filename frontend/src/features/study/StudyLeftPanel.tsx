import { Link } from 'react-router-dom'
import { ArrowLeft, ChevronLeft, ChevronRight, Clock } from 'lucide-react'
import { StatusPill } from '@/components/ui/StatusPill'
import { ProgressBar } from '@/components/ui/ProgressBar'
import { IconButton } from '@/components/ui/IconButton'
import type { Course, Topic } from '@/types/course'
import type { ActivityEntry } from '@/types/study'

interface StudyLeftPanelProps {
  course: Course
  currentWeekId: string
  currentTopicId: string | null
  onSelectTopic: (topic: Topic) => void
  collapsed: boolean
  onToggleCollapsed: () => void
  recentActivity: ActivityEntry[]
  progressPercent: number
}

export function StudyLeftPanel({
  course,
  currentWeekId,
  currentTopicId,
  onSelectTopic,
  collapsed,
  onToggleCollapsed,
  recentActivity,
  progressPercent,
}: StudyLeftPanelProps) {
  const week = course.units.flatMap((u) => u.weeks).find((w) => w.id === currentWeekId)
  const unit = course.units.find((u) => u.weeks.some((w) => w.id === currentWeekId))

  if (collapsed) {
    return (
      <div className="flex w-14 shrink-0 flex-col items-center gap-3 border-r border-surface-200 bg-surface-50 py-4">
        <IconButton icon={<ChevronRight className="h-4 w-4" />} label="Expandir panel" onClick={onToggleCollapsed} />
      </div>
    )
  }

  return (
    <aside className="flex w-72 shrink-0 flex-col border-r border-surface-200 bg-surface-50">
      <div className="flex items-center justify-between border-b border-surface-200 px-4 py-3.5">
        <Link
          to={`/cursos/${course.slug}`}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-700 hover:text-brand-600 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500 rounded"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Volver al curso
        </Link>
        <IconButton icon={<ChevronLeft className="h-4 w-4" />} label="Contraer panel" onClick={onToggleCollapsed} size="sm" />
      </div>

      <div className="border-b border-surface-200 px-4 py-3.5">
        <p className="text-xs font-medium text-ink-500">
          Unidad {unit?.number} · Semana {week?.number}
        </p>
        <h2 className="mt-0.5 text-sm font-semibold text-ink-900">{week?.theme}</h2>
        <p className="mt-0.5 text-xs text-ink-500">{week?.dateRange}</p>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3.5">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-500">Temas de la semana</h3>
        <ul className="space-y-1">
          {week?.topics.map((topic) => (
            <li key={topic.id}>
              <button
                type="button"
                onClick={() => onSelectTopic(topic)}
                aria-current={topic.id === currentTopicId ? 'true' : undefined}
                className={`w-full rounded-lg px-3 py-2 text-left text-sm transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500 ${
                  topic.id === currentTopicId ? 'bg-brand-50 text-brand-700' : 'text-ink-700 hover:bg-surface-200'
                }`}
              >
                <span className="block truncate font-medium">{topic.title}</span>
                <span className="mt-1 block">
                  <StatusPill status={topic.status} compact />
                </span>
              </button>
            </li>
          ))}
          {week?.topics.length === 0 && <li className="px-3 py-2 text-sm text-ink-500">Sin temas registrados esta semana.</li>}
        </ul>

        {recentActivity.length > 0 && (
          <div className="mt-6">
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-500">Historial reciente</h3>
            <ul className="space-y-2">
              {recentActivity.slice(0, 4).map((entry) => (
                <li key={entry.id} className="flex items-start gap-2 text-xs text-ink-500">
                  <Clock className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
                  <span className="line-clamp-2">{entry.summary}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="border-t border-surface-200 px-4 py-3.5">
        <ProgressBar percent={progressPercent} label="Progreso del curso" size="sm" />
      </div>
    </aside>
  )
}
