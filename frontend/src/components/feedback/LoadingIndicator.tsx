import { Loader2 } from 'lucide-react'

/** Indicador de "el tutor está pensando". aria-live se coloca en el
 * contenedor padre de la conversación (ver ConversationThread), no aquí,
 * para no duplicar anuncios al lector de pantalla. */
export function LoadingIndicator({ label = 'Buscando en los materiales del curso…' }: { label?: string }) {
  return (
    <div className="flex items-center gap-2.5 text-sm text-ink-500">
      <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}
