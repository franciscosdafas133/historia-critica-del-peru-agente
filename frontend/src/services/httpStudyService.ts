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

export const httpStudyService: StudyService = {
  async askUnderstand(question, _topicId): Promise<UnderstandResponse> {
    const data = await preguntar(question, 'preguntar')
    const evidence = evidenceFromPaquetes(data.paquetes)
    const rawText = data.respuesta ?? data.error_generacion ?? (data.paquetes.length === 0 ? SIN_EVIDENCIA : '')
    return {
      answer: { mainIdea: '', explanation: '', example: '', checkQuestion: '' },
      evidence,
      confidence: confidenceFrom(evidence),
      rawText,
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
      feedback: data.respuesta ?? data.error_generacion ?? SIN_EVIDENCIA,
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
      prompt: data.respuesta ?? data.error_generacion ?? SIN_EVIDENCIA,
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
        prompt: data.respuesta ?? data.error_generacion ?? SIN_EVIDENCIA,
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
      question: data.respuesta ?? data.error_generacion ?? SIN_EVIDENCIA,
      answer: '',
      evidenceIds: [],
    }]
  },

  async submitDebateThesis(thesis, _topicId): Promise<DebateResponse> {
    const data = await preguntar(thesis, 'debate')
    const evidence = evidenceFromPaquetes(data.paquetes)
    const rawText = data.respuesta ?? data.error_generacion ?? (data.paquetes.length === 0 ? SIN_EVIDENCIA : '')
    return {
      restatedThesis: '',
      supportingEvidence: evidence,
      tensioningEvidence: [],
      verdict: '',
      closingQuestion: '',
      rawText,
    }
  },
}
