/**
 * Modelo de dominio: sesión de estudio, modos pedagógicos y evidencias.
 */
import type { MaterialType } from './course'

export type StudyMode = 'understand' | 'solve' | 'practice' | 'assess' | 'review' | 'debate'

export type MessageRole = 'student' | 'tutor'

export interface ConversationMessage {
  id: string
  role: MessageRole
  /** Contenido en texto simple; el renderer interpreta saltos de párrafo. */
  content: string
  createdAt: string
  /** Solo en mensajes del tutor: ids de evidencia que respaldan la respuesta. */
  evidenceIds?: string[]
  /** Estructura "Entender": idea principal / explicación / ejemplo / pregunta. */
  structured?: UnderstandAnswer
}

export interface UnderstandAnswer {
  mainIdea: string
  explanation: string
  example: string
  checkQuestion: string
}

export type EvidenceSupportLevel = 'direct' | 'context' | 'interpretation'

export interface Evidence {
  id: string
  referenceNumber: number
  materialTitle: string
  authors: string[]
  materialType: MaterialType
  location: string
  excerpt: string
  supportLevel: EvidenceSupportLevel
}

export type ConfidenceLevel = 'strong' | 'partial' | 'insufficient'

export interface ConfidenceState {
  level: ConfidenceLevel
  supportingCount: number
  hasInterpretation: boolean
}

export interface PracticeQuestion {
  id: string
  topicId: string
  prompt: string
  options?: string[]
  correctAnswer: string
  explanation: string
  evidenceIds: string[]
}

export interface QuickAction {
  id: string
  label: string
  icon: 'simplify' | 'example' | 'try' | 'quiz' | 'sources'
}

export interface AssessmentQuestion extends PracticeQuestion {
  studentAnswer?: string
  isCorrect?: boolean
}

export interface AssessmentResult {
  id: string
  courseId: string
  completedAt: string
  questions: AssessmentQuestion[]
  score: number
  strongTopicId: string | null
  weakTopicId: string | null
}

export interface ReviewCard {
  id: string
  topicId: string
  question: string
  answer: string
  evidenceIds: string[]
}

/** Modo "Debatir": el tutor reconstruye la tesis del estudiante, presenta
 * evidencia a favor y en contra, y cierra con una pregunta que obliga a
 * decidir entre lecturas en conflicto — nunca cierra el debate por él.
 *
 * `rawText`, cuando está presente, es la respuesta real del backend en
 * prosa narrativa (reconstrucción de tesis, sostiene/tensiona, veredicto y
 * pregunta ya vienen implícitos en el texto, no como campos separados —
 * forzar al LLM a esa separación arriesgaría romper la garantía de citas
 * [n] del núcleo del agente). Los campos estructurados siguen existiendo
 * para el modo simulado (mock), que no tiene esa restricción. */
export interface DebateResponse {
  restatedThesis: string
  supportingEvidence: Evidence[]
  tensioningEvidence: Evidence[]
  verdict: string
  closingQuestion: string
  rawText?: string
}

export interface ProgressSummary {
  courseId: string
  overallPercent: number
  topicsUnderstood: number
  topicsTotal: number
  weeklyMinutesStudied: number
  lastTopicId: string | null
  lastMode: StudyMode | null
  topicsNeedingReview: string[]
}

export interface ActivityEntry {
  id: string
  courseId: string
  mode: StudyMode
  topicId: string | null
  summary: string
  timestamp: string
}
