import { useEffect, useState } from 'react'
import { ClipboardCheck, Trophy, RefreshCcw } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { ProgressBar } from '@/components/ui/ProgressBar'
import { LoadingIndicator } from '@/components/feedback/LoadingIndicator'
import { studyService } from '@/services/studyService'
import { progressService } from '@/services/progressService'
import type { AssessmentQuestion, AssessmentResult } from '@/types/study'

interface AssessModeProps {
  courseId: string
  onActivity: (summary: string) => void
}

type Phase = 'loading' | 'in_progress' | 'result'

/** Modo "Evaluarme": tres preguntas, sin revelar la respuesta correcta hasta
 * que el alumno responde cada una, con resultado final guardado en
 * localStorage vía progressService. */
export function AssessMode({ courseId, onActivity }: AssessModeProps) {
  const [phase, setPhase] = useState<Phase>('loading')
  const [questions, setQuestions] = useState<AssessmentQuestion[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [selected, setSelected] = useState<string | null>(null)
  const [revealed, setRevealed] = useState(false)

  function loadAssessment() {
    setPhase('loading')
    setCurrentIndex(0)
    setSelected(null)
    setRevealed(false)
    studyService.getAssessmentQuestions(null).then((qs) => {
      // Repite preguntas si el banco simulado tiene menos de 3, para cumplir
      // el requisito de "microevaluación de 3 preguntas" en esta fase.
      const filled: AssessmentQuestion[] = Array.from({ length: 3 }, (_, i) => ({ ...qs[i % qs.length], id: `${qs[i % qs.length].id}-${i}` }))
      setQuestions(filled)
      setPhase('in_progress')
    })
  }

  useEffect(loadAssessment, [])

  function handleReveal() {
    if (!selected) return
    setRevealed(true)
    setQuestions((prev) =>
      prev.map((q, i) => (i === currentIndex ? { ...q, studentAnswer: selected, isCorrect: selected === q.correctAnswer } : q)),
    )
  }

  function handleNext() {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex((i) => i + 1)
      setSelected(null)
      setRevealed(false)
    } else {
      finishAssessment()
    }
  }

  function finishAssessment() {
    const correct = questions.filter((q) => q.isCorrect).length
    const score = Math.round((correct / questions.length) * 100)
    const strong = questions.find((q) => q.isCorrect)?.topicId ?? null
    const weak = questions.find((q) => !q.isCorrect)?.topicId ?? null

    const result: AssessmentResult = {
      id: `assess-${Date.now()}`,
      courseId,
      completedAt: new Date().toISOString(),
      questions,
      score,
      strongTopicId: strong,
      weakTopicId: weak,
    }
    progressService.saveAssessmentResult(result)
    onActivity(`Completaste una microevaluación con ${score}% de aciertos`)
    setPhase('result')
  }

  if (phase === 'loading') {
    return (
      <div className="flex flex-1 items-center justify-center px-6 py-16">
        <LoadingIndicator label="Preparando tu microevaluación…" />
      </div>
    )
  }

  if (phase === 'result') {
    const correct = questions.filter((q) => q.isCorrect).length
    const score = Math.round((correct / questions.length) * 100)
    const strongTopic = questions.find((q) => q.isCorrect)
    const weakTopic = questions.find((q) => !q.isCorrect)

    return (
      <div className="flex flex-1 flex-col items-center gap-5 overflow-y-auto px-4 py-10 text-center md:px-6" aria-live="polite">
        <span className="flex h-14 w-14 items-center justify-center rounded-full bg-positive-50 text-positive-600">
          <Trophy className="h-7 w-7" aria-hidden="true" />
        </span>
        <div>
          <h2 className="text-lg font-semibold text-ink-900">Evaluación completada</h2>
          <p className="mt-1 text-sm text-ink-500">
            Respondiste {correct} de {questions.length} preguntas correctamente.
          </p>
        </div>
        <div className="w-full max-w-xs">
          <ProgressBar percent={score} label="Resultado" colorClassName={score >= 60 ? 'bg-positive-500' : 'bg-attention-500'} />
        </div>

        <div className="grid w-full max-w-sm grid-cols-1 gap-3 text-left sm:grid-cols-2">
          {strongTopic && (
            <div className="rounded-lg bg-positive-50 px-3.5 py-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-positive-600">Tema fuerte</p>
              <p className="mt-0.5 text-sm text-ink-900">{strongTopic.prompt.slice(0, 50)}…</p>
            </div>
          )}
          {weakTopic && (
            <div className="rounded-lg bg-attention-50 px-3.5 py-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-attention-600">Necesita refuerzo</p>
              <p className="mt-0.5 text-sm text-ink-900">{weakTopic.prompt.slice(0, 50)}…</p>
            </div>
          )}
        </div>

        <Button icon={<RefreshCcw className="h-4 w-4" />} variant="secondary" onClick={loadAssessment}>
          Intentar otra evaluación
        </Button>
      </div>
    )
  }

  const question = questions[currentIndex]

  return (
    <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-4 py-5 md:px-6" aria-live="polite">
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-brand-600">
          <ClipboardCheck className="h-3.5 w-3.5" aria-hidden="true" /> Microevaluación
        </h3>
        <span className="text-xs font-medium text-ink-500">
          {currentIndex + 1} de {questions.length}
        </span>
      </div>
      <ProgressBar percent={((currentIndex + (revealed ? 1 : 0)) / questions.length) * 100} size="sm" />

      <div className="rounded-xl border border-surface-200 bg-surface-50 p-5">
        <p className="mb-4 text-sm font-medium leading-relaxed text-ink-900">{question.prompt}</p>

        <fieldset className="space-y-2" disabled={revealed}>
          <legend className="sr-only">Opciones de respuesta</legend>
          {question.options?.map((option) => {
            const isCorrectOption = revealed && option === question.correctAnswer
            const isWrongSelected = revealed && selected === option && option !== question.correctAnswer
            return (
              <label
                key={option}
                className={`flex cursor-pointer items-center gap-2.5 rounded-lg border px-3.5 py-2.5 text-sm transition-colors duration-150 ${
                  isCorrectOption
                    ? 'border-positive-300 bg-positive-50 text-positive-700'
                    : isWrongSelected
                      ? 'border-attention-300 bg-attention-50 text-attention-700'
                      : selected === option
                        ? 'border-brand-400 bg-brand-50'
                        : 'border-surface-300 bg-surface-100 hover:border-brand-300'
                }`}
              >
                <input
                  type="radio"
                  name={`assess-option-${currentIndex}`}
                  value={option}
                  checked={selected === option}
                  onChange={() => setSelected(option)}
                  className="h-4 w-4 accent-brand-600"
                />
                {option}
              </label>
            )
          })}
        </fieldset>

        {!revealed ? (
          <Button className="mt-4" onClick={handleReveal} disabled={!selected}>
            Responder
          </Button>
        ) : (
          <div className="mt-4 space-y-3">
            <p className="text-sm text-ink-700">{question.explanation}</p>
            <Button onClick={handleNext}>{currentIndex < questions.length - 1 ? 'Siguiente pregunta' : 'Ver resultado'}</Button>
          </div>
        )}
      </div>
    </div>
  )
}
