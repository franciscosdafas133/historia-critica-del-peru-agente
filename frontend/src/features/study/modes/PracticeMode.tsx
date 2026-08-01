import { useEffect, useState } from 'react'
import { Dumbbell, CheckCircle2, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { LoadingIndicator } from '@/components/feedback/LoadingIndicator'
import { progressService } from '@/services/progressService'
import { studyService } from '@/services/studyService'
import type { PracticeFeedback } from '@/services/studyService'
import type { Evidence, PracticeQuestion } from '@/types/study'

interface PracticeModeProps {
  topicId: string | null
  onEvidenceUpdate: (evidence: Evidence[]) => void
  onActivity: (summary: string) => void
}

/** Modo "Practicar": una pregunta de opción múltiple por vez, corrección
 * inmediata con explicación, y actualización del progreso simulado. */
export function PracticeMode({ topicId, onEvidenceUpdate, onActivity }: PracticeModeProps) {
  const [question, setQuestion] = useState<PracticeQuestion | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<PracticeFeedback | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isChecking, setIsChecking] = useState(false)

  useEffect(() => {
    setIsLoading(true)
    setSelected(null)
    setFeedback(null)
    studyService.getPracticeQuestion(topicId).then((q) => {
      setQuestion(q)
      setIsLoading(false)
    })
  }, [topicId])

  async function handleCheck() {
    if (!question || !selected) return
    setIsChecking(true)
    const result = await studyService.submitPracticeAnswer(question, selected)
    setFeedback(result)
    onEvidenceUpdate(result.evidence)
    onActivity(result.isCorrect ? 'Respondiste correctamente en Practicar' : 'Practicaste una pregunta para reforzar')

    if (result.isCorrect) {
      const progress = progressService.getProgress()
      progressService.updateProgress({ topicsUnderstood: Math.min(progress.topicsUnderstood + 1, progress.topicsTotal) })
    }
    setIsChecking(false)
  }

  function handleNext() {
    setIsLoading(true)
    setSelected(null)
    setFeedback(null)
    studyService.getPracticeQuestion(topicId).then((q) => {
      setQuestion(q)
      setIsLoading(false)
    })
  }

  return (
    <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-4 py-5 md:px-6" aria-live="polite">
      {isLoading ? (
        <div className="rounded-xl border border-surface-200 bg-surface-50 p-5">
          <LoadingIndicator label="Preparando una pregunta…" />
        </div>
      ) : question ? (
        <div className="rounded-xl border border-surface-200 bg-surface-50 p-5">
          <h3 className="mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-brand-600">
            <Dumbbell className="h-3.5 w-3.5" aria-hidden="true" /> Pregunta de práctica
          </h3>
          <p className="mb-4 text-sm font-medium leading-relaxed text-ink-900">{question.prompt}</p>

          <fieldset className="space-y-2" disabled={Boolean(feedback)}>
            <legend className="sr-only">Opciones de respuesta</legend>
            {question.options?.map((option) => {
              const isSelected = selected === option
              const isCorrectOption = feedback && option === question.correctAnswer
              const isWrongSelected = feedback && isSelected && !feedback.isCorrect

              return (
                <label
                  key={option}
                  className={`flex cursor-pointer items-center gap-2.5 rounded-lg border px-3.5 py-2.5 text-sm transition-colors duration-150 ${
                    isCorrectOption
                      ? 'border-positive-300 bg-positive-50 text-positive-700'
                      : isWrongSelected
                        ? 'border-attention-300 bg-attention-50 text-attention-700'
                        : isSelected
                          ? 'border-brand-400 bg-brand-50'
                          : 'border-surface-300 bg-surface-100 hover:border-brand-300'
                  }`}
                >
                  <input
                    type="radio"
                    name="practice-option"
                    value={option}
                    checked={isSelected}
                    onChange={() => setSelected(option)}
                    className="h-4 w-4 accent-brand-600"
                  />
                  {option}
                  {isCorrectOption && <CheckCircle2 className="ml-auto h-4 w-4 shrink-0 text-positive-600" aria-hidden="true" />}
                  {isWrongSelected && <XCircle className="ml-auto h-4 w-4 shrink-0 text-attention-600" aria-hidden="true" />}
                </label>
              )
            })}
          </fieldset>

          {!feedback && (
            <div className="mt-4">
              <Button onClick={handleCheck} disabled={!selected || isChecking}>
                {isChecking ? 'Revisando…' : 'Comprobar respuesta'}
              </Button>
            </div>
          )}

          {feedback && (
            <div
              className={`mt-4 space-y-2 rounded-lg px-3.5 py-3 ${
                feedback.isCorrect ? 'bg-positive-50' : 'bg-attention-50'
              }`}
            >
              <p className={`text-sm font-semibold ${feedback.isCorrect ? 'text-positive-700' : 'text-attention-700'}`}>
                {feedback.isCorrect ? '¡Correcto!' : 'No es la respuesta correcta'}
              </p>
              <p className="text-sm text-ink-700">{feedback.explanation}</p>
              <Button variant="secondary" size="sm" onClick={handleNext} className="mt-2">
                Siguiente pregunta
              </Button>
            </div>
          )}
        </div>
      ) : null}
    </div>
  )
}
