import { FileText, ExternalLink } from 'lucide-react'
import { MaterialTypeBadge } from '@/components/ui/MaterialTypeBadge'
import type { Evidence } from '@/types/study'

const SUPPORT_LABELS: Record<Evidence['supportLevel'], { label: string; className: string }> = {
  direct: { label: 'Respaldo directo', className: 'text-positive-600' },
  context: { label: 'Contexto complementario', className: 'text-brand-600' },
  interpretation: { label: 'Interpretación', className: 'text-tutor-600' },
}

export function EvidenceCard({ evidence, onViewSource }: { evidence: Evidence; onViewSource: (evidence: Evidence) => void }) {
  const support = SUPPORT_LABELS[evidence.supportLevel]

  return (
    <article className="rounded-lg border border-surface-200 bg-surface-50 p-3.5">
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-brand-50 text-[11px] font-semibold text-brand-600">
            {evidence.referenceNumber}
          </span>
          <MaterialTypeBadge type={evidence.materialType} />
        </div>
        <span className={`text-xs font-medium ${support.className}`}>{support.label}</span>
      </div>

      <h3 className="text-sm font-semibold text-ink-900">{evidence.materialTitle}</h3>
      {evidence.authors.length > 0 && <p className="mt-0.5 text-xs text-ink-500">{evidence.authors.join(', ')}</p>}
      <p className="mt-0.5 text-xs text-ink-500">{evidence.location}</p>

      <blockquote className="mt-2 line-clamp-3 border-l-2 border-surface-300 pl-2.5 text-sm text-ink-700 italic">
        “{evidence.excerpt}”
      </blockquote>

      <button
        type="button"
        onClick={() => onViewSource(evidence)}
        className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-brand-600 hover:text-brand-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500 rounded"
      >
        <FileText className="h-3.5 w-3.5" aria-hidden="true" />
        Ver fuente
        <ExternalLink className="h-3 w-3" aria-hidden="true" />
      </button>
    </article>
  )
}
