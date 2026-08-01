import { CalendarClock } from 'lucide-react'
import { Card } from '@/components/ui/Card'

/** Próxima actividad simulada — refleja la semana de exámenes real del
 * cronograma (Semana 8), no una fecha inventada. */
export function NextActivityCard() {
  return (
    <Card className="border-brand-100 bg-brand-50">
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-600 text-white">
          <CalendarClock className="h-4.5 w-4.5" aria-hidden="true" />
        </span>
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-brand-600">Próxima evaluación</p>
          <p className="mt-0.5 text-sm font-semibold text-ink-900">Examen parcial — Semana 8</p>
          <p className="mt-0.5 text-xs text-ink-500">Cubre las unidades 1 y 2 vistas hasta la semana 7</p>
        </div>
      </div>
    </Card>
  )
}
