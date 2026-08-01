import { Link } from 'react-router-dom'
import { CompassIcon } from 'lucide-react'
import { Button } from '@/components/ui/Button'

export function NotFoundPage() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 px-6 py-16 text-center">
      <CompassIcon className="h-10 w-10 text-ink-300" aria-hidden="true" />
      <h1 className="text-lg font-semibold text-ink-900">Página no encontrada</h1>
      <p className="max-w-sm text-sm text-ink-500">La ruta que buscas no existe en este piloto.</p>
      <Link to="/">
        <Button variant="secondary" size="sm">
          Volver al inicio
        </Button>
      </Link>
    </div>
  )
}
