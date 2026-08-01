/**
 * Persistencia simulada de progreso, actividad, evaluaciones y repaso.
 * Usa localStorage exclusivamente — ver src/config/storage.config.ts para
 * las claves centralizadas. Ninguna otra parte de la app debe leer/escribir
 * localStorage directamente.
 */
import { STORAGE_KEYS } from '@/config/storage.config'
import type { ActivityEntry, AssessmentResult, ProgressSummary, StudyMode } from '@/types/study'

function readJSON<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return fallback
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

function writeJSON(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // localStorage puede fallar en modo privado o por cuota; degradar en silencio
    // es aceptable en esta fase de simulación (no hay datos críticos en juego).
  }
}

const DEFAULT_PROGRESS: ProgressSummary = {
  courseId: 'crs-122005',
  overallPercent: 0,
  topicsUnderstood: 0,
  topicsTotal: 13,
  weeklyMinutesStudied: 0,
  lastTopicId: null,
  lastMode: null,
  topicsNeedingReview: [],
}

export const progressService = {
  getProgress(): ProgressSummary {
    return readJSON(STORAGE_KEYS.progress, DEFAULT_PROGRESS)
  },

  updateProgress(patch: Partial<ProgressSummary>): ProgressSummary {
    const current = progressService.getProgress()
    const next = { ...current, ...patch }
    writeJSON(STORAGE_KEYS.progress, next)
    return next
  },

  getLastMode(): StudyMode | null {
    return readJSON<StudyMode | null>(STORAGE_KEYS.lastMode, null)
  },

  setLastMode(mode: StudyMode): void {
    writeJSON(STORAGE_KEYS.lastMode, mode)
    progressService.updateProgress({ lastMode: mode })
  },

  getReviewFlags(): string[] {
    return readJSON<string[]>(STORAGE_KEYS.reviewFlags, [])
  },

  flagForReview(topicId: string): void {
    const flags = progressService.getReviewFlags()
    if (!flags.includes(topicId)) {
      writeJSON(STORAGE_KEYS.reviewFlags, [...flags, topicId])
    }
  },

  clearReviewFlag(topicId: string): void {
    const flags = progressService.getReviewFlags().filter((id) => id !== topicId)
    writeJSON(STORAGE_KEYS.reviewFlags, flags)
  },

  getAssessmentResults(): AssessmentResult[] {
    return readJSON<AssessmentResult[]>(STORAGE_KEYS.assessmentResults, [])
  },

  saveAssessmentResult(result: AssessmentResult): void {
    const results = progressService.getAssessmentResults()
    writeJSON(STORAGE_KEYS.assessmentResults, [result, ...results].slice(0, 10))
  },

  getRecentActivity(): ActivityEntry[] {
    return readJSON<ActivityEntry[]>(STORAGE_KEYS.recentActivity, [])
  },

  logActivity(entry: ActivityEntry): void {
    const activity = progressService.getRecentActivity()
    writeJSON(STORAGE_KEYS.recentActivity, [entry, ...activity].slice(0, 20))
  },
}
