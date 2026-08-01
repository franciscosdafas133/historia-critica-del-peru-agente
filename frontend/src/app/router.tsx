import { Routes, Route } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { DashboardPage } from './pages/DashboardPage'
import { CoursePage } from './pages/CoursePage'
import { StudyPage } from './pages/StudyPage'
import { HistoryPage } from './pages/HistoryPage'
import { ProgressPage } from './pages/ProgressPage'
import { SettingsPage } from './pages/SettingsPage'
import { NotFoundPage } from './pages/NotFoundPage'

/** La Sala de Estudio (/estudiar) no usa AppShell: tiene su propio layout de
 * tres columnas a pantalla completa (ver StudyShell), sin sidebar/header
 * genérico encima. El resto de rutas sí comparte AppShell. */
export function AppRouter() {
  return (
    <Routes>
      <Route path="/cursos/:courseSlug/estudiar" element={<StudyPage />} />
      <Route
        path="/*"
        element={
          <AppShell>
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/cursos/:courseSlug" element={<CoursePage />} />
              <Route path="/historial" element={<HistoryPage />} />
              <Route path="/progreso" element={<ProgressPage />} />
              <Route path="/configuracion" element={<SettingsPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </AppShell>
        }
      />
    </Routes>
  )
}
