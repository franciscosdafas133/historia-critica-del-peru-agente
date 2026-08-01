import type { LucideIcon } from 'lucide-react'
import { Construction } from 'lucide-react'

interface ComingSoonProps {
  title: string
  description: string
  icon?: LucideIcon
}

/** Usar solo para funciones genuinamente no implementadas en este piloto.
 * Nunca como sustituto de un botón roto: si algo aparece en la navegación,
 * debe llevar aquí explícitamente, nunca a un enlace muerto. */
export function ComingSoon({ title, description, icon: Icon = Construction }: ComingSoonProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-surface-300 bg-surface-50 px-6 py-16 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-surface-200 text-ink-500">
        <Icon className="h-6 w-6" aria-hidden="true" />
      </span>
      <h2 className="text-base font-semibold text-ink-900">{title}</h2>
      <p className="max-w-sm text-sm text-ink-500">{description}</p>
      <span className="mt-1 inline-flex items-center rounded-full bg-attention-50 px-3 py-1 text-xs font-medium text-attention-600">
        Próximamente
      </span>
    </div>
  )
}
