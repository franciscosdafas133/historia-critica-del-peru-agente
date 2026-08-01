import { useEffect, useState } from 'react'
import { RotateCcw, Eye, CheckCircle2, RefreshCcw } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { LoadingIndicator } from '@/components/feedback/LoadingIndicator'
import { progressService } from '@/services/progressService'
import { studyService } from '@/services/studyService'
import type { ReviewCard } from '@/types/study'

interface ReviewModeProps {
  topicId: string | null
  onActivity: (summary: string) => void
}

/** Modo "Repasar": tarjetas pregunta/respuesta con dos botones de
 * autoevaluación que actualizan las banderas de repaso en localStorage. */
export function ReviewMode({ topicId, onActivity }: ReviewModeProps) {
  const [cards, setCards] = useState<ReviewCard[]>([])
  const [index, setIndex] = useState(0)
  const [revealed, setRevealed] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [completed, setCompleted] = useState<Record<string, 'remembered' | 'needs_review'>>({})

  useEffect(() => {
    setIsLoading(true)
    studyService.getReviewCards(topicId).then((c) => {
      setCards(c)
      setIndex(0)
      setRevealed(false)
      setCompleted({})
      setIsLoading(false)
    })
  }, [topicId])

  function handleResponse(remembered: boolean) {
    const card = cards[index]
    setCompleted((prev) => ({ ...prev, [card.id]: remembered ? 'remembered' : 'needs_review' }))

    if (remembered) {
      progressService.clearReviewFlag(card.topicId)
    } else {
      progressService.flagForReview(card.topicId)
    }

    if (index < cards.length - 1) {
      setIndex((i) => i + 1)
      setRevealed(false)
    } else {
      onActivity('Completaste una sesión de repaso rápido')
    }
  }

  function restart() {
    setIndex(0)
    setRevealed(false)
    setCompleted({})
  }

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center px-6 py-16">
        <LoadingIndicator label="Preparando tarjetas de repaso…" />
      </div>
    )
  }

  if (cards.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 py-16 text-center">
        <RotateCcw className="h-8 w-8 text-ink-300" aria-hidden="true" />
        <p className="text-sm text-ink-500">No tienes conceptos pendientes de repaso por ahora.</p>
      </div>
    )
  }

  const isDone = Object.keys(completed).length === cards.length
  const card = cards[Math.min(index, cards.length - 1)]

  if (isDone) {
    const rememberedCount = Object.values(completed).filter((v) => v === 'remembered').length
    return (
      <div className="flex flex-1 flex-col items-center gap-4 px-6 py-16 text-center" aria-live="polite">
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-positive-50 text-positive-600">
          <CheckCircle2 className="h-6 w-6" aria-hidden="true" />
        </span>
        <p className="text-sm text-ink-700">
          Repasaste {cards.length} conceptos. Recordabas {rememberedCount} de {cards.length}.
        </p>
        <Button variant="secondary" icon={<RefreshCcw className="h-4 w-4" />} onClick={restart}>
          Repasar de nuevo
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col items-center gap-5 overflow-y-auto px-4 py-8 md:px-6" aria-live="polite">
      <span className="text-xs font-medium text-ink-500">
        Tarjeta {index + 1} de {cards.length}
      </span>

      <div className="flex w-full max-w-md min-h-[220px] flex-col justify-center rounded-xl border border-surface-200 bg-surface-50 p-6 text-center shadow-soft">
        <p className="text-xs font-semibold uppercase tracking-wide text-tutor-600">Pregunta</p>
        <p className="mt-2 text-base font-medium leading-relaxed text-ink-900">{card.question}</p>

        {revealed && (
          <>
            <div className="my-4 h-px bg-surface-200" />
            <p className="text-xs font-semibold uppercase tracking-wide text-positive-600">Respuesta</p>
            <p className="mt-2 text-sm leading-relaxed text-ink-700">{card.answer}</p>
          </>
        )}
      </div>

      {!revealed ? (
        <Button icon={<Eye className="h-4 w-4" />} onClick={() => setRevealed(true)}>
          Mostrar respuesta
        </Button>
      ) : (
        <div className="flex gap-3">
          <Button variant="outline" onClick={() => handleResponse(false)}>
            Necesito repasarlo
          </Button>
          <Button variant="primary" onClick={() => handleResponse(true)}>
            Lo recuerdo
          </Button>
        </div>
      )}
    </div>
  )
}
