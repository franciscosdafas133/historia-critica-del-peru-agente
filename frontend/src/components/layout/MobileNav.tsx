import { NavLink } from 'react-router-dom'
import { Home, BookOpen, History, TrendingUp, Settings } from 'lucide-react'

const NAV_ITEMS = [
  { to: '/', label: 'Inicio', icon: Home, end: true },
  { to: '/cursos/historia-critica-del-peru', label: 'Curso', icon: BookOpen, end: false },
  { to: '/historial', label: 'Historial', icon: History, end: false },
  { to: '/progreso', label: 'Progreso', icon: TrendingUp, end: false },
  { to: '/configuracion', label: 'Ajustes', icon: Settings, end: false },
]

/** Barra de navegación inferior para móvil (<768px). Áreas táctiles ≥44px. */
export function MobileNav() {
  return (
    <nav
      aria-label="Navegación principal"
      className="fixed inset-x-0 bottom-0 z-40 flex border-t border-surface-200 bg-surface-50/95 backdrop-blur-sm md:hidden"
      style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
    >
      {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            `flex flex-1 flex-col items-center gap-1 py-2.5 text-[11px] font-medium transition-colors duration-150 ${
              isActive ? 'text-brand-600' : 'text-ink-500'
            }`
          }
        >
          <Icon className="h-5 w-5" aria-hidden="true" />
          {label}
        </NavLink>
      ))}
    </nav>
  )
}
