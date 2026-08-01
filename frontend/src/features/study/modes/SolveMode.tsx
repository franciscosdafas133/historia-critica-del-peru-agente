import { useEffect, useState } from 'react'
import { Compass, Lightbulb, CheckCircle2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { LoadingIndicator } from '@/components/feedback/LoadingIndicator'
import { studyService } from '@/services/studyService'
import type { SolveFeedback, SolveHint } from '@/services/studyService'

export const SOLVE_PROMPT =
  '¿Por qué la crisis demográfica del siglo XVI en los Andes fue más profunda que en otras regiones colonizadas por Europa en el mismo periodo?'
const PROMPT = SOLVE_PROMPT

interface SolveModeProps {
  topicId: string | null
  onActivity: (summary: string) => void
}

/** Modo "Resolver": el alumno analiza una pregunta con pistas progresivas
 * antes de escribir su propio intento — el tutor nunca entrega la respuesta
 * directamente, solo retroalimentación sobre lo que el alumno ya escribió. */
export function SolveMode({ topicId, onActivity }: SolveModeProps) {
  const [hints, setHints] = useState<SolveHint[]>([])
  const [visibleHints, setVisibleHints] = useState(0)
  const [attempt, setAttempt] = useState('')
  const [feedback, setFeedback] = useState<SolveFeedback | null>(null)
  const [isLoadingHints, setIsLoadingHints] = useState(true)
  const [isComparing, setIsComparing] = useState(false)

  useEffect(() => {
    setIsLoadingHints(true)
    setVisibleHints(0)
    setFeedback(null)
    setAttempt('')
    studyService.getSolveHints(topicId).then((h) => {
      setHints(h)
      setIsLoadingHints(false)
    })
  }, [topicId])

  async function handleCompare() {
    if (!attempt.trim()) return
    setIsComparing(true)
    const result = await studyService.submitSolveAttempt(attempt, topicId)
    setFeedback(result)
    onActivity('Comparaste tu análisis en el modo Resolver')
    setIsComparing(false)
  }

  return (
    <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-4 py-5 md:px-6" aria-live="polite">
      <div className="rounded-xl border border-surface-200 bg-surface-50 p-5">
        <h3 className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-brand-600">
          <Compass className="h-3.5 w-3.5" aria-hidden="true" /> Pregunta para analizar
        </h3>
        <p className="text-sm leading-relaxed text-ink-900">{PROMPT}</p>
      </div>

      <div className="rounded-xl border border-surface-200 bg-surface-50 p-5">
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-500">Pistas</h3>
        {isLoadingHints ? (
          <LoadingIndicator label="Preparando pistas…" />
        ) : (
          <div className="space-y-2.5">
            {hints.slice(0, Math.max(visibleHints, 1)).map((hint) => (
              <div key={hint.order} className="flex items-start gap-2.5 rounded-lg bg-brand-50 px-3.5 py-2.5">
                <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" aria-hidden="true" />
                <p className="text-sm text-brand-700">{hint.text}</p>
              </div>
            ))}
            {visibleHints < hints.length - 1 && (
              <Button variant="outline" size="sm" onClick={() => setVisibleHints((v) => v + 1)}>
                Mostrar otra pista
              </Button>
            )}
          </div>
        )}
      </div>

      <div className="rounded-xl border border-surface-200 bg-surface-50 p-5">
        <label htmlFor="solve-attempt" className="mb-2 block text-xs font-semibold uppercase tracking-wide text-ink-500">
          Tu intento
        </label>
        <textarea
          id="solve-attempt"
          value={attempt}
          onChange={(e) => setAttempt(e.target.value)}
          rows={4}
          placeholder="Desarrolla tu propia respuesta antes de compararla…"
          className="w-full resize-none rounded-lg border border-surface-300 bg-surface-100 px-3.5 py-2.5 text-sm text-ink-900 placeholder:text-ink-300 focus:border-brand-400 focus:outline-none"
        />
        <div className="mt-3">
          <Button onClick={handleCompare} disabled={!attempt.trim() || isComparing}>
            {isComparing ? 'Comparando…' : 'Comparar mi respuesta'}
          </Button>
        </div>
      </div>

      {isComparing && (
        <div className="rounded-xl border border-surface-200 bg-surface-50 p-5">
          <LoadingIndicator label="Analizando tu respuesta…" />
        </div>
      )}

      {feedback && !isComparing && (
        <div className="space-y-3 rounded-xl border border-positive-100 bg-positive-50 p-5">
          <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-positive-600">
            <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" /> Retroalimentación
          </h3>
          <p className="text-sm leading-relaxed text-ink-900">{feedback.feedback}</p>
          {feedback.gaps.length > 0 && (
            <div>
              <p className="text-xs font-medium text-ink-500">Para profundizar:</p>
              <ul className="mt-1 list-inside list-disc space-y-1 text-sm text-ink-700">
                {feedback.gaps.map((gap, i) => (
                  <li key={i}>{gap}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
