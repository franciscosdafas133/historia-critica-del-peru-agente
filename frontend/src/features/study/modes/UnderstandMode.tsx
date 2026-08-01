import { useState } from 'react'
import { Lightbulb, BookOpenText, Sparkles, HelpCircle } from 'lucide-react'
import { ChatInput } from '../ChatInput'
import { QuickActions } from '../QuickActions'
import { FormattedAnswer } from '../FormattedAnswer'
import { LoadingIndicator } from '@/components/feedback/LoadingIndicator'
import { SkeletonText } from '@/components/ui/Skeleton'
import { ConfidenceBadge } from '@/features/evidence/ConfidenceBadge'
import { studyService } from '@/services/studyService'
import type { UnderstandResponse } from '@/services/studyService'
import type { Evidence } from '@/types/study'

interface UnderstandModeProps {
  topicId: string | null
  onEvidenceUpdate: (evidence: Evidence[]) => void
  onActivity: (summary: string) => void
}

/** Modo "Entender": explicación estructurada en idea principal / explicación
 * / ejemplo / pregunta de comprobación, siempre con evidencias visibles. */
export function UnderstandMode({ topicId, onEvidenceUpdate, onActivity }: UnderstandModeProps) {
  const [question, setQuestion] = useState<string | null>(null)
  const [response, setResponse] = useState<UnderstandResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  async function ask(q: string) {
    setQuestion(q)
    setIsLoading(true)
    setResponse(null)
    const result = await studyService.askUnderstand(q, topicId)
    setResponse(result)
    onEvidenceUpdate(result.evidence)
    onActivity(`Preguntaste: "${q.slice(0, 60)}${q.length > 60 ? '…' : ''}"`)
    setIsLoading(false)
  }

  function handleQuickAction(actionId: string) {
    if (actionId === 'simplify') ask('Explícamelo de forma más sencilla')
    else if (actionId === 'example') ask('Dame otro ejemplo de esto')
    else if (actionId === 'quiz') ask('Hazme una pregunta sobre este tema')
  }

  return (
    <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-4 py-5 md:px-6" aria-live="polite">
      {!question && (
        <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-surface-300 py-14 text-center">
          <Lightbulb className="h-8 w-8 text-tutor-300" aria-hidden="true" />
          <p className="max-w-sm text-sm text-ink-500">
            Escribe una pregunta sobre el tema de la semana. El tutor la explicará con las fuentes del curso.
          </p>
        </div>
      )}

      {question && (
        <div className="rounded-xl bg-brand-50 px-4 py-3 text-sm text-brand-700">
          <span className="font-medium">Tú preguntaste: </span>
          {question}
        </div>
      )}

      {isLoading && (
        <div className="rounded-xl border border-surface-200 bg-surface-50 p-5">
          <LoadingIndicator />
          <div className="mt-4">
            <SkeletonText lines={4} />
          </div>
        </div>
      )}

      {response && !isLoading && (
        <div className="space-y-4 rounded-xl border border-surface-200 bg-surface-50 p-5">
          <ConfidenceBadge confidence={response.confidence} />

          {response.rawText ? (
            <FormattedAnswer text={response.rawText} />
          ) : (
            <>
              <section>
                <h3 className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-tutor-600">
                  <Sparkles className="h-3.5 w-3.5" aria-hidden="true" /> Idea principal
                </h3>
                <p className="text-sm leading-relaxed text-ink-900">{response.answer.mainIdea}</p>
              </section>

              <section>
                <h3 className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-tutor-600">
                  <BookOpenText className="h-3.5 w-3.5" aria-hidden="true" /> Explicación
                </h3>
                <p className="text-sm leading-relaxed text-ink-700">{response.answer.explanation}</p>
              </section>

              <section className="rounded-lg bg-surface-100 px-3.5 py-3">
                <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-500">Ejemplo</h3>
                <p className="text-sm leading-relaxed text-ink-700">{response.answer.example}</p>
              </section>

              <section className="flex items-start gap-2 rounded-lg border border-tutor-100 bg-tutor-50 px-3.5 py-3">
                <HelpCircle className="mt-0.5 h-4 w-4 shrink-0 text-tutor-600" aria-hidden="true" />
                <p className="text-sm font-medium text-tutor-700">{response.answer.checkQuestion}</p>
              </section>
            </>
          )}

          <QuickActions onAction={(a) => handleQuickAction(a.id)} />
        </div>
      )}

      <div className="mt-auto pt-2">
        <ChatInput onSubmit={ask} placeholder="Pregunta algo sobre el tema…" disabled={isLoading} />
      </div>
    </div>
  )
}
