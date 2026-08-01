import type { HTMLAttributes, ReactNode } from 'react'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  padded?: boolean
  hoverable?: boolean
}

export function Card({ children, padded = true, hoverable = false, className = '', ...props }: CardProps) {
  return (
    <div
      className={`rounded-xl border border-surface-300 bg-surface-50 shadow-soft ${padded ? 'p-5' : ''} ${
        hoverable ? 'transition-shadow duration-150 hover:shadow-soft-lg' : ''
      } ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}
