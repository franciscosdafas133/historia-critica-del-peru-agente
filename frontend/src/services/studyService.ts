/**
 * Abstracción de acceso a la lógica de estudio: respuestas del tutor,
 * pistas, práctica, evaluación y repaso.
 *
 * Todo aquí es simulado (`mockStudyService`). El contrato de funciones está
 * diseñado para que conectar un backend real (recuperación + LLM) solo
 * requiera una nueva implementación de `StudyService`, no cambios en los
 * componentes de features/study.
 */
import type { DebateResponse, Evidence, ConfidenceState, PracticeQuestion, ReviewCard, UnderstandAnswer } from '@/types/study'
import { MOCK_DEBATE_RESPONSE, MOCK_EVIDENCE, MOCK_PRACTICE_QUESTIONS, MOCK_REVIEW_CARDS, MOCK_UNDERSTAND_ANSWER } from '@/mocks/studyData'
import { delay } from './delay'
import { confidenceFrom } from './evidenceMapping'
import { API_BASE_URL } from '@/config/api.config'
import { httpStudyService } from './httpStudyService'

export interface UnderstandResponse {
  answer: UnderstandAnswer
  evidence: Evidence[]
  confidence: ConfidenceState
  /** Presente solo cuando la respuesta viene del backend real: texto narrativo
   * completo del tutor, con sus citas [n] ya embebidas. Cuando existe, el
   * componente lo muestra en vez de los 4 campos separados de `answer`
   * (que el backend no produce sin arriesgar romper esa garantía de citas). */
  rawText?: string
  /** El motor se abstuvo: la pregunta queda fuera de lo que cubre el material
   * del curso. No es un error — es el límite funcionando. Se marca aparte del
   * texto para que la interfaz pueda distinguirlo de una respuesta normal:
   * si se muestra igual que una explicación, el estudiante no sabe si el
   * agente falló o si preguntó algo fuera de alcance. */
  outOfScope?: boolean
}

export interface SolveHint {
  order: number
  text: string
}

export interface SolveFeedback {
  feedback: string
  strengths: string[]
  gaps: string[]
}

export interface PracticeFeedback {
  isCorrect: boolean
  explanation: string
  evidence: Evidence[]
}

export interface StudyService {
  askUnderstand: (question: string, topicId: string | null) => Promise<UnderstandResponse>
  getSolveHints: (topicId: string | null) => Promise<SolveHint[]>
  submitSolveAttempt: (attempt: string, topicId: string | null) => Promise<SolveFeedback>
  getPracticeQuestion: (topicId: string | null) => Promise<PracticeQuestion>
  submitPracticeAnswer: (question: PracticeQuestion, answer: string) => Promise<PracticeFeedback>
  getAssessmentQuestions: (topicId: string | null) => Promise<PracticeQuestion[]>
  getReviewCards: (topicId: string | null) => Promise<ReviewCard[]>
  submitDebateThesis: (thesis: string, topicId: string | null) => Promise<DebateResponse>
}

const SOLVE_HINTS: SolveHint[] = [
  { order: 1, text: 'Piensa en qué factores hacían más vulnerable a la población frente a una enfermedad nueva.' },
  { order: 2, text: 'Considera cómo la desestructuración del trabajo agrícola pudo agravar —no solo acompañar— la crisis sanitaria.' },
  { order: 3, text: 'Revisa si el argumento del material distingue causa inicial de factores que profundizaron la crisis.' },
]

function pickEvidence(ids: string[]): Evidence[] {
  return ids.map((id) => MOCK_EVIDENCE[id]).filter((e): e is Evidence => Boolean(e))
}

export const mockStudyService: StudyService = {
  async askUnderstand(_question, _topicId) {
    await delay(650)
    const evidence = pickEvidence(['ev-1', 'ev-2', 'ev-3'])
    return {
      answer: MOCK_UNDERSTAND_ANSWER,
      evidence,
      confidence: confidenceFrom(evidence),
    }
  },

  async getSolveHints(_topicId) {
    await delay(300)
    return SOLVE_HINTS
  },

  async submitSolveAttempt(attempt, _topicId) {
    await delay(600)
    const hasLength = attempt.trim().length > 40
    return {
      feedback: hasLength
        ? 'Tu respuesta identifica bien el factor sanitario. Para fortalecerla, podrías precisar cómo interactuó con la organización del trabajo colonial —eso es lo que distingue una causa de un factor agravante.'
        : 'Tu intento es breve. Antes de comparar con el material, intenta desarrollar la relación entre al menos dos factores (por ejemplo, epidemia y trabajo forzado) en vez de nombrarlos por separado.',
      strengths: hasLength ? ['Identifica correctamente el factor sanitario como punto de partida.'] : [],
      gaps: ['Falta conectar explícitamente el factor demográfico con la reorganización colonial del trabajo.'],
    }
  },

  async getPracticeQuestion(topicId) {
    await delay(400)
    const match = MOCK_PRACTICE_QUESTIONS.find((q) => q.topicId === topicId)
    return match ?? MOCK_PRACTICE_QUESTIONS[0]
  },

  async submitPracticeAnswer(question, answer) {
    await delay(500)
    const isCorrect = answer.trim().toLowerCase() === question.correctAnswer.trim().toLowerCase()
    return {
      isCorrect,
      explanation: question.explanation,
      evidence: pickEvidence(question.evidenceIds),
    }
  },

  async getAssessmentQuestions(_topicId) {
    await delay(400)
    return MOCK_PRACTICE_QUESTIONS
  },

  async getReviewCards(topicId) {
    await delay(350)
    if (!topicId) return MOCK_REVIEW_CARDS
    const filtered = MOCK_REVIEW_CARDS.filter((c) => c.topicId === topicId)
    return filtered.length > 0 ? filtered : MOCK_REVIEW_CARDS
  },

  async submitDebateThesis(_thesis, _topicId) {
    await delay(700)
    return MOCK_DEBATE_RESPONSE
  },
}

export const studyService: StudyService = API_BASE_URL ? httpStudyService : mockStudyService
