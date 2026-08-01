import { Info, FileText } from 'lucide-react'
import { Modal } from '@/components/ui/Modal'
import { MaterialTypeBadge } from '@/components/ui/MaterialTypeBadge'
import type { Evidence } from '@/types/study'

interface SourcePreviewModalProps {
  evidence: Evidence | null
  onClose: () => void
}

export function SourcePreviewModal({ evidence, onClose }: SourcePreviewModalProps) {
  if (!evidence) return null

  return (
    <Modal isOpen={Boolean(evidence)} onClose={onClose} title="Vista previa de la fuente">
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-ink-900">{evidence.materialTitle}</h3>
            {evidence.authors.length > 0 && <p className="text-xs text-ink-500">{evidence.authors.join(', ')}</p>}
            <p className="text-xs text-ink-500">{evidence.location}</p>
          </div>
          <MaterialTypeBadge type={evidence.materialType} />
        </div>

        <div className="flex aspect-[4/3] items-center justify-center rounded-lg border border-dashed border-surface-300 bg-surface-100">
          <div className="flex flex-col items-center gap-2 px-6 text-center">
            <FileText className="h-8 w-8 text-ink-300" aria-hidden="true" />
            <p className="text-sm text-ink-500">Previsualización del documento</p>
          </div>
        </div>

        <blockquote className="rounded-lg border-l-2 border-brand-300 bg-brand-50 px-3.5 py-3 text-sm text-ink-700 italic">
          “{evidence.excerpt}”
        </blockquote>

        <div className="flex items-start gap-2.5 rounded-lg bg-attention-50 px-3.5 py-3 text-sm text-attention-600">
          <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <p>
            Vista previa del prototipo. La apertura del documento original se conectará en la fase backend.
          </p>
        </div>
      </div>
    </Modal>
  )
}
