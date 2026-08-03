import { Lightbulb, Compass, Dumbbell, ClipboardCheck, RotateCcw, Swords } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { StudyMode } from '@/types/study'

interface ModeConfig {
  id: StudyMode
  label: string
  description: string
  icon: LucideIcon
}

// Solo "Entender" esta habilitado mientras se evalua el metodo de
// recuperacion FORMA-IR: se prueba un unico modo a la vez para que
// cualquier resultado sea atribuible a la recuperacion y no a las
// diferencias de prompt entre modos. Los demas modos siguen
// implementados (features/study/modes/*.tsx) -- para reactivarlos basta
// devolver sus entradas a esta lista.
//
// Pendiente conocido en el modo Resolver: la retroalimentacion llega con
// caracteres corruptos ("ÂÂÂ...", UTF-8 interpretado como Latin-1). Debe
// arreglarse antes de rehabilitarlo.
export const STUDY_MODES: ModeConfig[] = [
  { id: 'understand', label: 'Entender', description: 'Explicación guiada con evidencias', icon: Lightbulb },
]

export const STUDY_MODES_DESHABILITADOS: ModeConfig[] = [
  { id: 'solve', label: 'Resolver', description: 'Analiza una fuente paso a paso', icon: Compass },
  { id: 'practice', label: 'Practicar', description: 'Responde y recibe retroalimentación', icon: Dumbbell },
  { id: 'assess', label: 'Evaluarme', description: 'Microevaluación de 3 preguntas', icon: ClipboardCheck },
  { id: 'review', label: 'Repasar', description: 'Tarjetas de repaso rápido', icon: RotateCcw },
  { id: 'debate', label: 'Debatir', description: 'Confronta tu tesis con la evidencia', icon: Swords },
]

interface StudyModeSelectorProps {
  activeMode: StudyMode
  onSelectMode: (mode: StudyMode) => void
}

export function StudyModeSelector({ activeMode, onSelectMode }: StudyModeSelectorProps) {
  return (
    <div role="tablist" aria-label="Modo de estudio" className="flex gap-1.5 overflow-x-auto px-4 py-3 md:px-6">
      {STUDY_MODES.map(({ id, label, description, icon: Icon }) => {
        const isActive = id === activeMode
        return (
          <button
            key={id}
            role="tab"
            aria-selected={isActive}
            title={description}
            onClick={() => onSelectMode(id)}
            className={`flex shrink-0 items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500 ${
              isActive ? 'bg-tutor-500 text-white shadow-soft' : 'bg-surface-200 text-ink-700 hover:bg-surface-300'
            }`}
          >
            <Icon className="h-4 w-4" aria-hidden="true" />
            {label}
          </button>
        )
      })}
    </div>
  )
}
