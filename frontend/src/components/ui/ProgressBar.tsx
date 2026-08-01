interface ProgressBarProps {
  percent: number
  label?: string
  size?: 'sm' | 'md'
  colorClassName?: string
}

export function ProgressBar({ percent, label, size = 'md', colorClassName = 'bg-brand-500' }: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, percent))
  const height = size === 'sm' ? 'h-1.5' : 'h-2.5'

  return (
    <div className="w-full">
      {label && (
        <div className="mb-1.5 flex items-center justify-between text-xs text-ink-500">
          <span>{label}</span>
          <span className="font-medium text-ink-700">{clamped}%</span>
        </div>
      )}
      <div
        className={`w-full overflow-hidden rounded-full bg-surface-200 ${height}`}
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label ?? `Progreso: ${clamped}%`}
      >
        <div
          className={`h-full rounded-full transition-[width] duration-500 motion-reduce:transition-none ${colorClassName}`}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  )
}
