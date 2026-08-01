/**
 * Claves centralizadas de localStorage. Ningún componente debe escribir
 * un string literal de clave directamente: todas pasan por aquí para
 * evitar colisiones y para que quede claro, en un solo lugar, qué persiste
 * la app en esta fase de simulación.
 */
export const STORAGE_KEYS = {
  theme: 'nexo.theme',
  progress: 'nexo.progress',
  lastMode: 'nexo.lastMode',
  assessmentResults: 'nexo.assessmentResults',
  reviewFlags: 'nexo.reviewFlags',
  recentActivity: 'nexo.recentActivity',
} as const
