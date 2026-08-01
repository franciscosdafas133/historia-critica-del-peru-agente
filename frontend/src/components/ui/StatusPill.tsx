import { Check, Circle, RefreshCw, AlertCircle } from 'lucide-react'
import type { TopicStatus } from '@/types/course'

const STATUS_CONFIG: Record<TopicStatus, { label: string; icon: typeof Check; className: string }> = {
  not_started: {
    label: 'No iniciado',
    icon: Circle,
    className: 'bg-surface-200 text-ink-500',
  },
  in_progress: {
    label: 'En proceso',
    icon: RefreshCw,
    className: 'bg-brand-50 text-brand-600',
  },
  understood: {
    label: 'Comprendido',
    icon: Check,
    className: 'bg-positive-50 text-positive-600',
  },
  needs_review: {
    label: 'Necesita refuerzo',
    icon: AlertCircle,
    className: 'bg-attention-50 text-attention-600',
  },
}

export function StatusPill({ status, compact = false }: { status: TopicStatus; compact?: boolean }) {
  const config = STATUS_CONFIG[status]
  const Icon = config.icon
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-medium ${config.className} ${
        compact ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs'
      }`}
    >
      <Icon className={compact ? 'h-3 w-3' : 'h-3.5 w-3.5'} aria-hidden="true" />
      {config.label}
    </span>
  )
}
