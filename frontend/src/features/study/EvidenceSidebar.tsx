import { FileStack } from 'lucide-react'
import { EvidencePanel } from '@/features/evidence/EvidencePanel'
import type { Evidence } from '@/types/study'

interface EvidenceSidebarProps {
  evidence: Evidence[]
  onViewSource: (evidence: Evidence) => void
}

/** Panel derecho de escritorio. En móvil/tablet, el mismo contenido se
 * renderiza dentro de un Drawer desde StudyPage — ver useMediaQuery. */
export function EvidenceSidebar({ evidence, onViewSource }: EvidenceSidebarProps) {
  return (
    <aside className="hidden w-80 shrink-0 flex-col border-l border-surface-200 bg-surface-50 lg:flex">
      <div className="flex items-center gap-2 border-b border-surface-200 px-4 py-3.5">
        <FileStack className="h-4 w-4 text-ink-500" aria-hidden="true" />
        <h2 className="text-sm font-semibold text-ink-900">Evidencias</h2>
        {evidence.length > 0 && (
          <span className="ml-auto rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-600">
            {evidence.length}
          </span>
        )}
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-4">
        <EvidencePanel evidence={evidence} onViewSource={onViewSource} />
      </div>
    </aside>
  )
}
