import { FileStack } from 'lucide-react'

interface EvidenceFloatingButtonProps {
  count: number
  onClick: () => void
}

/** Botón para abrir el drawer de evidencias en pantallas <1024px.
 * Visible incluso con 0 evidencias, para que el alumno sepa que el panel
 * existe antes de hacer su primera pregunta. */
export function EvidenceFloatingButton({ count, onClick }: EvidenceFloatingButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="fixed bottom-20 right-4 z-30 flex items-center gap-2 rounded-full bg-brand-600 px-4 py-2.5 text-sm font-medium text-white shadow-soft-lg transition-transform duration-150 hover:scale-105 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-700 md:bottom-6 lg:hidden"
    >
      <FileStack className="h-4 w-4" aria-hidden="true" />
      Evidencias
      {count > 0 && (
        <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-white px-1 text-xs font-semibold text-brand-600">
          {count}
        </span>
      )}
    </button>
  )
}
