import { NavLink } from 'react-router-dom'
import { Home, BookOpen, History, TrendingUp, Settings, GraduationCap } from 'lucide-react'
import { APP_CONFIG } from '@/config/app.config'

const NAV_ITEMS = [
  { to: '/', label: 'Inicio', icon: Home, end: true },
  { to: '/cursos/historia-critica-del-peru', label: 'Mi curso', icon: BookOpen, end: false },
  { to: '/historial', label: 'Historial', icon: History, end: false },
  { to: '/progreso', label: 'Progreso', icon: TrendingUp, end: false },
  { to: '/configuracion', label: 'Configuración', icon: Settings, end: false },
]

/** Navegación principal, fija en escritorio. En móvil se renderiza aparte
 * como MobileNav (barra inferior) — ver AppShell. */
export function Sidebar() {
  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-surface-200 bg-surface-50 md:flex">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">
          <GraduationCap className="h-4.5 w-4.5" aria-hidden="true" />
        </span>
        <span className="text-sm font-semibold tracking-tight text-ink-900">{APP_CONFIG.productName}</span>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-2" aria-label="Navegación principal">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors duration-150 ${
                isActive ? 'bg-brand-50 text-brand-600' : 'text-ink-700 hover:bg-surface-200'
              }`
            }
          >
            <Icon className="h-4.5 w-4.5 shrink-0" aria-hidden="true" />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
