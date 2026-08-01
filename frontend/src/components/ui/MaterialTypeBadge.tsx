import type { MaterialType } from '@/types/course'

const LABELS: Record<MaterialType, string> = {
  clase: 'Clase',
  lectura: 'Lectura',
  evaluacion: 'Evaluación',
  guion: 'Guion',
  rector: 'Documento oficial',
}

const CLASSES: Record<MaterialType, string> = {
  clase: 'bg-brand-50 text-brand-600',
  lectura: 'bg-tutor-50 text-tutor-600',
  evaluacion: 'bg-attention-50 text-attention-600',
  guion: 'bg-positive-50 text-positive-600',
  rector: 'bg-surface-200 text-ink-700',
}

export function MaterialTypeBadge({ type }: { type: MaterialType }) {
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${CLASSES[type]}`}>
      {LABELS[type]}
    </span>
  )
}
