import { FileText, ScanText } from 'lucide-react'
import { MaterialTypeBadge } from '@/components/ui/MaterialTypeBadge'
import type { Material } from '@/types/course'

export function RecentMaterialsGrid({ materials }: { materials: Material[] }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {materials.map((material) => (
        <div key={material.id} className="rounded-lg border border-surface-200 bg-surface-50 p-3.5">
          <div className="flex items-start justify-between gap-2">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-surface-200 text-ink-500">
              <FileText className="h-4 w-4" aria-hidden="true" />
            </span>
            <MaterialTypeBadge type={material.type} />
          </div>
          <h4 className="mt-2 line-clamp-2 text-sm font-medium text-ink-900">{material.title}</h4>
          {material.authors.length > 0 && <p className="mt-0.5 truncate text-xs text-ink-500">{material.authors.join(', ')}</p>}
          <div className="mt-2 flex items-center gap-2 text-xs text-ink-300">
            <span>{material.pageCount} pág.</span>
            {material.isScanned && (
              <span className="inline-flex items-center gap-1">
                <ScanText className="h-3 w-3" aria-hidden="true" /> escaneado
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
