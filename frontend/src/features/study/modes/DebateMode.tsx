import { useState } from 'react'
import { Swords, ShieldCheck, ShieldAlert, HelpCircle } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { LoadingIndicator } from '@/components/feedback/LoadingIndicator'
import { EvidenceCard } from '@/features/evidence/EvidenceCard'
import { FormattedAnswer } from '../FormattedAnswer'
import { studyService } from '@/services/studyService'
import type { DebateResponse, Evidence } from '@/types/study'

interface DebateModeProps {
  topicId: string | null
  onEvidenceUpdate: (evidence: Evidence[]) => void
  onActivity: (summary: string) => void
  onViewSource: (evidence: Evidence) => void
}

/** Modo "Debatir": el estudiante propone una tesis y el tutor la reconstruye,
 * confronta evidencia a favor y en contra, y cierra con una pregunta que no
 * resuelve el debate por él — refleja el modo de debate ya construido en el
 * backend (agente.py, MODO_DEBATE). */
export function DebateMode({ topicId, onEvidenceUpdate, onActivity, onViewSource }: DebateModeProps) {
  const [thesis, setThesis] = useState('')
  const [response, setResponse] = useState<DebateResponse | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit() {
    if (!thesis.trim()) return
    setIsSubmitting(true)
    const result = await studyService.submitDebateThesis(thesis, topicId)
    setResponse(result)
    onEvidenceUpdate([...result.supportingEvidence, ...result.tensioningEvidence])
    onActivity('Debatiste una tesis con el tutor')
    setIsSubmitting(false)
  }

  return (
    <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-4 py-5 md:px-6" aria-live="polite">
      <div className="rounded-xl border border-surface-200 bg-surface-50 p-5">
        <h3 className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-tutor-600">
          <Swords className="h-3.5 w-3.5" aria-hidden="true" /> Plantea tu tesis
        </h3>
        <p className="mb-3 text-sm text-ink-500">
          Escribe una postura sobre el tema —el tutor la reconstruirá y la confrontará con la evidencia disponible, a favor y en contra.
        </p>
        <label htmlFor="debate-thesis" className="sr-only">
          Tu tesis
        </label>
        <textarea
          id="debate-thesis"
          value={thesis}
          onChange={(e) => setThesis(e.target.value)}
          rows={3}
          placeholder="Por ejemplo: la epidemia fue el factor decisivo del colapso demográfico andino…"
          className="w-full resize-none rounded-lg border border-surface-300 bg-surface-100 px-3.5 py-2.5 text-sm text-ink-900 placeholder:text-ink-300 focus:border-tutor-400 focus:outline-none"
        />
        <div className="mt-3">
          <Button onClick={handleSubmit} disabled={!thesis.trim() || isSubmitting}>
            {isSubmitting ? 'Confrontando con la evidencia…' : 'Debatir esta tesis'}
          </Button>
        </div>
      </div>

      {isSubmitting && (
        <div className="rounded-xl border border-surface-200 bg-surface-50 p-5">
          <LoadingIndicator label="Reconstruyendo tu argumento…" />
        </div>
      )}

      {response && !isSubmitting && (
        <div className="space-y-4">
          {response.rawText ? (
            <div className="rounded-xl border border-surface-200 bg-surface-50 p-5">
              <FormattedAnswer text={response.rawText} />
            </div>
          ) : (
            <>
              <div className="rounded-xl border border-tutor-100 bg-tutor-50 p-5">
                <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-tutor-600">Tu tesis, reconstruida</h3>
                <p className="text-sm leading-relaxed text-ink-900">{response.restatedThesis}</p>
              </div>

              {response.supportingEvidence.length > 0 && (
                <div>
                  <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-positive-600">
                    <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" /> Lo que la sostiene
                  </h3>
                  <div className="space-y-2.5">
                    {response.supportingEvidence.map((e) => (
                      <EvidenceCard key={e.id} evidence={e} onViewSource={onViewSource} />
                    ))}
                  </div>
                </div>
              )}

              {response.tensioningEvidence.length > 0 && (
                <div>
                  <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-attention-600">
                    <ShieldAlert className="h-3.5 w-3.5" aria-hidden="true" /> Lo que la tensiona
                  </h3>
                  <div className="space-y-2.5">
                    {response.tensioningEvidence.map((e) => (
                      <EvidenceCard key={e.id} evidence={e} onViewSource={onViewSource} />
                    ))}
                  </div>
                </div>
              )}

              <div className="rounded-xl border border-surface-200 bg-surface-50 p-5">
                <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-500">Veredicto</h3>
                <p className="text-sm leading-relaxed text-ink-900">{response.verdict}</p>
              </div>

              <div className="rounded-xl border border-brand-100 bg-brand-50 p-5">
                <h3 className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-brand-600">
                  <HelpCircle className="h-3.5 w-3.5" aria-hidden="true" /> Para seguir debatiendo
                </h3>
                <p className="text-sm leading-relaxed text-ink-900">{response.closingQuestion}</p>
              </div>
            </>
          )}

          {response.rawText && (response.supportingEvidence.length > 0 || response.tensioningEvidence.length > 0) && (
            <div>
              <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-brand-600">
                <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" /> Evidencia consultada
              </h3>
              <div className="space-y-2.5">
                {[...response.supportingEvidence, ...response.tensioningEvidence].map((e) => (
                  <EvidenceCard key={e.id} evidence={e} onViewSource={onViewSource} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
