import { ShieldCheck, ShieldAlert, ShieldQuestion } from 'lucide-react'
import type { ConfidenceState } from '@/types/study'

/** Nunca muestra porcentajes de confianza inventados — solo estados
 * cualitativos derivados del número y tipo de evidencia recuperada. */
export function ConfidenceBadge({ confidence }: { confidence: ConfidenceState }) {
  if (confidence.level === 'insufficient') {
    return (
      <div className="flex items-center gap-2 rounded-lg bg-attention-50 px-3 py-2 text-sm text-attention-600">
        <ShieldQuestion className="h-4 w-4 shrink-0" aria-hidden="true" />
        <span>No encontré suficiente información en el curso para responder esto con seguridad.</span>
      </div>
    )
  }

  if (confidence.level === 'partial') {
    return (
      <div className="flex items-center gap-2 rounded-lg bg-attention-50 px-3 py-2 text-sm text-attention-600">
        <ShieldAlert className="h-4 w-4 shrink-0" aria-hidden="true" />
        <span>Evidencia parcial — respaldada por {confidence.supportingCount} fuente{confidence.supportingCount !== 1 ? 's' : ''} de contexto.</span>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2 rounded-lg bg-positive-50 px-3 py-2 text-sm text-positive-600">
      <ShieldCheck className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span>
        Respuesta respaldada por {confidence.supportingCount} fuente{confidence.supportingCount !== 1 ? 's' : ''} del curso
        {confidence.hasInterpretation ? ' — incluye una interpretación marcada como tal.' : '.'}
      </span>
    </div>
  )
}
