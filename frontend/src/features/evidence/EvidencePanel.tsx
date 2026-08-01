import { FileSearch } from 'lucide-react'
import { EvidenceCard } from './EvidenceCard'
import type { Evidence } from '@/types/study'

interface EvidencePanelProps {
  evidence: Evidence[]
  onViewSource: (evidence: Evidence) => void
}

export function EvidencePanel({ evidence, onViewSource }: EvidencePanelProps) {
  if (evidence.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 px-4 py-12 text-center">
        <FileSearch className="h-8 w-8 text-ink-300" aria-hidden="true" />
        <p className="text-sm text-ink-500">Las evidencias de tu próxima pregunta aparecerán aquí.</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {evidence.map((e) => (
        <EvidenceCard key={e.id} evidence={e} onViewSource={onViewSource} />
      ))}
    </div>
  )
}
