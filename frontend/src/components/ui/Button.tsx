import { forwardRef } from 'react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'

type Variant = 'primary' | 'secondary' | 'tutor' | 'ghost' | 'outline'
type Size = 'sm' | 'md' | 'lg'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  icon?: ReactNode
  iconPosition?: 'left' | 'right'
}

const VARIANT_CLASSES: Record<Variant, string> = {
  primary: 'bg-brand-600 text-white hover:bg-brand-700 focus-visible:outline-brand-600 shadow-soft',
  secondary: 'bg-surface-200 text-ink-900 hover:bg-surface-300 focus-visible:outline-ink-500',
  tutor: 'bg-tutor-500 text-white hover:bg-tutor-600 focus-visible:outline-tutor-500 shadow-soft',
  ghost: 'bg-transparent text-ink-700 hover:bg-surface-200 focus-visible:outline-ink-500',
  outline: 'bg-transparent border border-surface-300 text-ink-900 hover:bg-surface-100 focus-visible:outline-brand-500',
}

const SIZE_CLASSES: Record<Size, string> = {
  sm: 'text-sm px-3 py-1.5 gap-1.5 rounded-md',
  md: 'text-sm px-4 py-2.5 gap-2 rounded-lg',
  lg: 'text-base px-5 py-3 gap-2 rounded-lg',
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', icon, iconPosition = 'left', className = '', children, disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled}
        className={`inline-flex items-center justify-center font-medium transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap ${VARIANT_CLASSES[variant]} ${SIZE_CLASSES[size]} ${className}`}
        {...props}
      >
        {icon && iconPosition === 'left' && <span className="shrink-0" aria-hidden="true">{icon}</span>}
        {children}
        {icon && iconPosition === 'right' && <span className="shrink-0" aria-hidden="true">{icon}</span>}
      </button>
    )
  },
)
Button.displayName = 'Button'
