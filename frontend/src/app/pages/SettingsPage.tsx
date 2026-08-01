import { useEffect } from 'react'
import { Settings, Sun, Moon, User, Bell } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { ComingSoon } from '@/components/feedback/ComingSoon'
import { useTheme } from '@/hooks/useTheme'
import { MOCK_STUDENT } from '@/mocks/studentData'
import { APP_CONFIG } from '@/config/app.config'

export function SettingsPage() {
  const { theme, setTheme } = useTheme()

  useEffect(() => {
    document.title = `Configuración · ${APP_CONFIG.productName}`
  }, [])

  return (
    <div className="mx-auto max-w-2xl space-y-6 px-4 py-6 md:px-8 md:py-8">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-semibold text-ink-900">
          <Settings className="h-5 w-5 text-ink-500" aria-hidden="true" /> Configuración
        </h1>
        <p className="mt-1 text-sm text-ink-500">Sesión de {MOCK_STUDENT.fullName}</p>
      </div>

      <Card>
        <h2 className="mb-3 text-sm font-semibold text-ink-900">Apariencia</h2>
        <div role="radiogroup" aria-label="Tema de la aplicación" className="grid grid-cols-2 gap-3">
          <button
            type="button"
            role="radio"
            aria-checked={theme === 'light'}
            onClick={() => setTheme('light')}
            className={`flex flex-col items-center gap-2 rounded-lg border px-4 py-4 text-sm font-medium transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500 ${
              theme === 'light' ? 'border-brand-400 bg-brand-50 text-brand-700' : 'border-surface-300 text-ink-700 hover:bg-surface-100'
            }`}
          >
            <Sun className="h-5 w-5" aria-hidden="true" />
            Claro
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={theme === 'dark'}
            onClick={() => setTheme('dark')}
            className={`flex flex-col items-center gap-2 rounded-lg border px-4 py-4 text-sm font-medium transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500 ${
              theme === 'dark' ? 'border-brand-400 bg-brand-50 text-brand-700' : 'border-surface-300 text-ink-700 hover:bg-surface-100'
            }`}
          >
            <Moon className="h-5 w-5" aria-hidden="true" />
            Oscuro
          </button>
        </div>
      </Card>

      <ComingSoon
        title="Perfil y notificaciones"
        description="La edición de perfil y las preferencias de notificación se conectarán cuando exista autenticación real."
        icon={User}
      />
      <ComingSoon
        title="Preferencias de estudio"
        description="Ajustes de recordatorios y metas semanales llegarán en la fase de backend."
        icon={Bell}
      />
    </div>
  )
}
