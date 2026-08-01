import type { ReactNode } from 'react'
import { Sidebar } from './Sidebar'
import { MobileNav } from './MobileNav'
import { AppHeader } from './AppHeader'

/** Layout de aplicación estándar: sidebar + header + contenido con scroll
 * propio, más navegación inferior en móvil. La Sala de Estudio usa su propio
 * layout de tres columnas (ver features/study/StudyShell) porque necesita
 * el alto completo de la ventana sin el padding de este shell. */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-surface-100">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <AppHeader />
        <main className="flex-1 overflow-y-auto pb-20 md:pb-0">{children}</main>
      </div>
      <MobileNav />
    </div>
  )
}
