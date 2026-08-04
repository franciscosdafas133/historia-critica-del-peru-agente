/**
 * Implementación real de StudyService: llama al backend Flask
 * (agente.py + recuperar.py + proveedor.py) vía /api/preguntar.
 *
 * El backend no separa su respuesta en campos estructurados para los modos
 * narrativos (Entender, Resolver, Debatir) — devuelve texto libre con citas
 * [n], porque forzar JSON arriesgaría romper esa garantía de citas del
 * núcleo del agente (ver agente.py, NUCLEO). Practicar/Evaluar/Repasar sí
 * llegan estructurados (`estructurado` en la respuesta) porque el prompt les
 * pide un formato de marcadores parseable en el servidor.
 */
import type { StudyService, UnderstandResponse, SolveHint, SolveFeedback, PracticeFeedback } from './studyService'
import type { DebateResponse, PracticeQuestion, ReviewCard } from '@/types/study'
import { API_BASE_URL } from '@/config/api.config'
import { evidenceFromPaquetes, confidenceFrom, type BackendPaquete } from './evidenceMapping'
import { practiceTopicPrompt, assessTopicPrompt, reviewTopicPrompt } from './topicPrompts'
import { SOLVE_PROMPT } from '@/features/study/modes/SolveMode'

interface BackendRespuesta {
  pregunta: string
  modo: string
  paquetes: BackendPaquete[]
  avisos: string[]
  respuesta: string | null
  error_generacion: string | null
  estructurado: { prompt: string; options: string[]; correctAnswer: string; explanation: string; evidenceIds: number[] }
    | { question: string; answer: string; evidenceIds: number[] }
    | null
}

async function preguntar(pregunta: string, modo: string): Promise<BackendRespuesta> {
  const res = await fetch(`${API_BASE_URL}/api/preguntar`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pregunta, modo, generar: true }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error ?? `Error del servidor (${res.status})`)
  }
  return res.json()
}

const SIN_EVIDENCIA = 'El material autorizado del curso no cubre esta consulta.'
const CUOTA_AGOTADA =
  'El tutor alcanzó el límite de consultas gratuitas por hoy. Vuelve a intentarlo en unos minutos o mañana.'
const ERROR_GENERICO = 'Hubo un problema generando la respuesta. Inténtalo de nuevo en unos momentos.'

/** El backend expone el error crudo del proveedor (traceback de Python) en
 * `error_generacion` — nunca se muestra tal cual al estudiante. Se traduce
 * a un mensaje breve y accionable; el caso de cuota agotada (429) es el más
 * común en el tier gratuito y merece un mensaje específico. */
function friendlyError(raw: string): string {
  if (/RESOURCE_EXHAUSTED|429|quota/i.test(raw)) return CUOTA_AGOTADA
  if (/413|rate_limit_exceeded|tokens per minute|too large/i.test(raw)) return CUOTA_AGOTADA
  return ERROR_GENERICO
}

function narrativeFrom(data: BackendRespuesta): string {
  if (data.respuesta) return data.respuesta
  if (data.error_generacion) return friendlyError(data.error_generacion)
  if (data.paquetes.length === 0) {
    // El motor explica POR QUÉ se abstuvo (tema fuera del corpus, o petición
    // del producto de una evaluación) en el primer aviso. Mostrar ese motivo
    // en vez del mensaje genérico: sin él, el estudiante veía una respuesta
    // vacía y no sabía si el agente falló o si su pregunta está fuera de
    // alcance — dos situaciones que exigen reacciones distintas.
    const motivo = data.avisos?.[0]
    return motivo ? motivo : SIN_EVIDENCIA
  }
  return ''
}

export const httpStudyService: StudyService = {
  async askUnderstand(question, _topicId): Promise<UnderstandResponse> {
    const data = await preguntar(question, 'preguntar')
    const evidence = evidenceFromPaquetes(data.paquetes)
    return {
      answer: { mainIdea: '', explanation: '', example: '', checkQuestion: '' },
      evidence,
      confidence: confidenceFrom(evidence),
      rawText: narrativeFrom(data),
    }
  },

  async getSolveHints(_topicId): Promise<SolveHint[]> {
    // Sin equivalente 1:1 en el backend: el intento del estudiante se manda
    // completo en submitSolveAttempt, no hay generacion de pistas por separado
    // en esta fase — decision de alcance documentada, no un bug.
    return []
  },

  async submitSolveAttempt(attempt, _topicId): Promise<SolveFeedback> {
    const pregunta = `${SOLVE_PROMPT}\n\nMi intento de respuesta: ${attempt}`
    const data = await preguntar(pregunta, 'resolver')
    return {
      feedback: narrativeFrom(data),
      strengths: [],
      gaps: [],
    }
  },

  async getPracticeQuestion(topicId): Promise<PracticeQuestion> {
    const data = await preguntar(practiceTopicPrompt(topicId), 'practicar')
    const est = data.estructurado as { prompt: string; options: string[]; correctAnswer: string; explanation: string; evidenceIds: number[] } | null
    if (est) {
      return {
        id: `practicar-${Date.now()}`,
        topicId: topicId ?? '',
        prompt: est.prompt,
        options: est.options,
        correctAnswer: est.correctAnswer,
        explanation: est.explanation,
        evidenceIds: est.evidenceIds.map(String),
      }
    }
    // Fallback: el LLM no siguio el formato esperado o no hay evidencia —
    // se degrada a mostrar el texto crudo sin opciones (el frontend ya tolera
    // options ausente, ver PracticeMode.tsx).
    return {
      id: `practicar-${Date.now()}`,
      topicId: topicId ?? '',
      prompt: narrativeFrom(data),
      correctAnswer: '',
      explanation: '',
      evidenceIds: [],
    }
  },

  async submitPracticeAnswer(question, answer): Promise<PracticeFeedback> {
    // No requiere llamada al backend: la comparacion ya se resuelve local,
    // igual que en el mock (la pregunta ya trajo su correctAnswer consigo).
    return {
      isCorrect: answer.trim().toLowerCase() === question.correctAnswer.trim().toLowerCase(),
      explanation: question.explanation,
      evidence: [],
    }
  },

  async getAssessmentQuestions(topicId): Promise<PracticeQuestion[]> {
    const results = await Promise.all(
      Array.from({ length: 3 }, () => preguntar(assessTopicPrompt(topicId), 'evaluar')),
    )
    return results.map((data, i) => {
      const est = data.estructurado as { prompt: string; options: string[]; correctAnswer: string; explanation: string; evidenceIds: number[] } | null
      if (est) {
        return {
          id: `evaluar-${Date.now()}-${i}`,
          topicId: topicId ?? '',
          prompt: est.prompt,
          options: est.options,
          correctAnswer: est.correctAnswer,
          explanation: est.explanation,
          evidenceIds: est.evidenceIds.map(String),
        }
      }
      return {
        id: `evaluar-${Date.now()}-${i}`,
        topicId: topicId ?? '',
        prompt: narrativeFrom(data),
        correctAnswer: '',
        explanation: '',
        evidenceIds: [],
      }
    })
  },

  async getReviewCards(topicId): Promise<ReviewCard[]> {
    const data = await preguntar(reviewTopicPrompt(topicId), 'repasar')
    const est = data.estructurado as { question: string; answer: string; evidenceIds: number[] } | null
    if (est) {
      return [{ id: `repasar-${Date.now()}`, topicId: topicId ?? '', question: est.question, answer: est.answer, evidenceIds: est.evidenceIds.map(String) }]
    }
    return [{
      id: `repasar-${Date.now()}`,
      topicId: topicId ?? '',
      question: narrativeFrom(data),
      answer: '',
      evidenceIds: [],
    }]
  },

  async submitDebateThesis(thesis, _topicId): Promise<DebateResponse> {
    const data = await preguntar(thesis, 'debate')
    const evidence = evidenceFromPaquetes(data.paquetes)
    return {
      restatedThesis: '',
      supportingEvidence: evidence,
      tensioningEvidence: [],
      verdict: '',
      closingQuestion: '',
      rawText: narrativeFrom(data),
    }
  },
}
