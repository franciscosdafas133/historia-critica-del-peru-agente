import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import { X } from 'lucide-react'
import { IconButton } from './IconButton'

interface DrawerProps {
  isOpen: boolean
  onClose: () => void
  title: string
  children: ReactNode
}

/** Bottom sheet para móvil/tablet: mismo contrato de accesibilidad que Modal
 * (foco atrapado, cierre con Escape) pero anclado al borde inferior. */
export function Drawer({ isOpen, onClose, title, children }: DrawerProps) {
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isOpen) return
    document.body.style.overflow = 'hidden'
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    panelRef.current?.querySelector<HTMLElement>('button')?.focus()
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = ''
    }
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-end">
      <div className="absolute inset-0 bg-ink-900/40" onClick={onClose} aria-hidden="true" />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="drawer-title"
        className="relative z-10 max-h-[85vh] w-full overflow-y-auto rounded-t-2xl border-t border-surface-300 bg-surface-50 shadow-soft-lg motion-safe:animate-drawer-in"
      >
        <div className="sticky top-0 flex items-center justify-between border-b border-surface-200 bg-surface-50 px-5 py-4">
          <h2 id="drawer-title" className="text-base font-semibold text-ink-900">
            {title}
          </h2>
          <IconButton icon={<X className="h-4 w-4" />} label="Cerrar" onClick={onClose} size="sm" />
        </div>
        <div className="px-5 py-4">{children}</div>
      </div>
    </div>
  )
}
