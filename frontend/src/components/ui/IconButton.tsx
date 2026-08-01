import { forwardRef } from 'react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon: ReactNode
  label: string
  variant?: 'ghost' | 'solid'
  size?: 'sm' | 'md'
}

/** Botón de solo icono. `label` es obligatorio: se usa como aria-label y
 * como tooltip nativo (title), como exige la guía de accesibilidad. */
export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ icon, label, variant = 'ghost', size = 'md', className = '', ...props }, ref) => {
    const sizeClass = size === 'sm' ? 'h-8 w-8' : 'h-10 w-10'
    const variantClass =
      variant === 'solid'
        ? 'bg-surface-200 hover:bg-surface-300 text-ink-900'
        : 'bg-transparent hover:bg-surface-200 text-ink-700'

    return (
      <button
        ref={ref}
        aria-label={label}
        title={label}
        className={`inline-flex items-center justify-center rounded-lg transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500 disabled:opacity-50 disabled:cursor-not-allowed ${sizeClass} ${variantClass} ${className}`}
        {...props}
      >
        {icon}
      </button>
    )
  },
)
IconButton.displayName = 'IconButton'
