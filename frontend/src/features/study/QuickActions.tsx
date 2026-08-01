import { Sparkles, Lightbulb, PenLine, HelpCircle, Library } from 'lucide-react'
import type { QuickAction } from '@/types/study'

const ACTIONS: QuickAction[] = [
  { id: 'simplify', label: 'Explícamelo más fácil', icon: 'simplify' },
  { id: 'example', label: 'Dame un ejemplo', icon: 'example' },
  { id: 'try', label: 'Quiero intentarlo', icon: 'try' },
  { id: 'quiz', label: 'Hazme una pregunta', icon: 'quiz' },
  { id: 'sources', label: 'Ver fuentes', icon: 'sources' },
]

const ICONS = {
  simplify: Sparkles,
  example: Lightbulb,
  try: PenLine,
  quiz: HelpCircle,
  sources: Library,
}

export function QuickActions({ onAction }: { onAction: (action: QuickAction) => void }) {
  return (
    <div className="flex flex-wrap gap-2" aria-label="Acciones sugeridas">
      {ACTIONS.map((action) => {
        const Icon = ICONS[action.icon]
        return (
          <button
            key={action.id}
            type="button"
            onClick={() => onAction(action)}
            className="inline-flex items-center gap-1.5 rounded-full border border-surface-300 bg-surface-50 px-3 py-1.5 text-xs font-medium text-ink-700 transition-colors duration-150 hover:border-tutor-300 hover:bg-tutor-50 hover:text-tutor-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-tutor-500"
          >
            <Icon className="h-3.5 w-3.5" aria-hidden="true" />
            {action.label}
          </button>
        )
      })}
    </div>
  )
}
