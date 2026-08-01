import { GraduationCap } from 'lucide-react'
import { ThemeToggle } from './ThemeToggle'
import { APP_CONFIG } from '@/config/app.config'
import { MOCK_STUDENT } from '@/mocks/studentData'

/** Cabecera compacta, visible en todas las vistas. En móvil sustituye al
 * bloque de marca de la Sidebar (que solo se muestra en escritorio). */
export function AppHeader() {
  const initials = MOCK_STUDENT.fullName
    .split(' ')
    .map((p) => p[0])
    .slice(0, 2)
    .join('')

  return (
    <header className="flex items-center justify-between border-b border-surface-200 bg-surface-50/80 px-4 py-3 backdrop-blur-sm md:px-6">
      <div className="flex items-center gap-2 md:hidden">
        <span className="flex h-7 w-7 items-center justify-center rounded-md bg-brand-600 text-white">
          <GraduationCap className="h-4 w-4" aria-hidden="true" />
        </span>
        <span className="text-sm font-semibold text-ink-900">{APP_CONFIG.productName}</span>
      </div>
      <div className="hidden md:block" />
      <div className="flex items-center gap-3">
        <ThemeToggle />
        <span
          className="flex h-8 w-8 items-center justify-center rounded-full bg-tutor-100 text-xs font-semibold text-tutor-700"
          aria-label={`Sesión de ${MOCK_STUDENT.fullName}`}
        >
          {initials}
        </span>
      </div>
    </header>
  )
}
