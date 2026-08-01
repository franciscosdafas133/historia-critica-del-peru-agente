import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronDown, Calendar, FileWarning } from 'lucide-react'
import { StatusPill } from '@/components/ui/StatusPill'
import type { Unit } from '@/types/course'

const UNIT_ACCENTS = ['border-l-unit-1', 'border-l-unit-2'] as const

export function UnitAccordion({ unit, index, courseSlug }: { unit: Unit; index: number; courseSlug: string }) {
  const [isOpen, setIsOpen] = useState(index === 0)
  const navigate = useNavigate()
  const accent = UNIT_ACCENTS[index % UNIT_ACCENTS.length]

  return (
    <div className={`overflow-hidden rounded-xl border border-surface-300 border-l-4 bg-surface-50 ${accent}`}>
      <button
        type="button"
        onClick={() => setIsOpen((o) => !o)}
        aria-expanded={isOpen}
        className="flex w-full items-center justify-between px-5 py-4 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-brand-500"
      >
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-ink-500">Unidad {unit.number}</p>
          <h3 className="mt-0.5 text-sm font-semibold text-ink-900">{unit.title}</h3>
        </div>
        <ChevronDown
          className={`h-4.5 w-4.5 shrink-0 text-ink-500 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
          aria-hidden="true"
        />
      </button>

      {isOpen && (
        <div className="space-y-2 border-t border-surface-200 px-5 py-4">
          {unit.weeks.map((week) => (
            <div key={week.id} className="rounded-lg bg-surface-100 px-4 py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-ink-500">Semana {week.number}</span>
                  <span className="inline-flex items-center gap-1 text-xs text-ink-300">
                    <Calendar className="h-3 w-3" aria-hidden="true" />
                    {week.dateRange}
                  </span>
                </div>
                {week.isExamWeek && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-attention-50 px-2 py-0.5 text-xs font-medium text-attention-600">
                    <FileWarning className="h-3 w-3" aria-hidden="true" />
                    Examen
                  </span>
                )}
              </div>
              <p className="mt-1 text-sm text-ink-900">{week.theme}</p>

              {week.topics.length > 0 && (
                <ul className="mt-2.5 flex flex-wrap gap-2">
                  {week.topics.map((topic) => (
                    <li key={topic.id}>
                      <button
                        type="button"
                        onClick={() => navigate(`/cursos/${courseSlug}/estudiar`)}
                        className="flex items-center gap-1.5 rounded-full bg-surface-50 border border-surface-300 px-2.5 py-1 text-xs text-ink-700 transition-colors duration-150 hover:border-brand-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500"
                      >
                        {topic.title}
                        <StatusPill status={topic.status} compact />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
