/**
 * Abstracción de acceso a datos de curso.
 *
 * `mockCourseService` es la única implementación en esta fase. Cuando exista
 * un backend real, se crea `httpCourseService` con la misma forma (mismo
 * contrato de funciones) y se sustituye la exportación por defecto sin tocar
 * ningún componente que ya la consuma.
 */
import type { Course, Material } from '@/types/course'
import { MATERIALS, PILOT_COURSE } from '@/mocks/courseData'
import { delay } from './delay'

export interface CourseService {
  getCourseBySlug: (slug: string) => Promise<Course | null>
  getMaterial: (materialId: string) => Promise<Material | null>
  getMaterialsByIds: (materialIds: string[]) => Promise<Material[]>
}

export const mockCourseService: CourseService = {
  async getCourseBySlug(slug) {
    await delay(300)
    return PILOT_COURSE.slug === slug ? PILOT_COURSE : null
  },

  async getMaterial(materialId) {
    await delay(150)
    return MATERIALS[materialId] ?? null
  },

  async getMaterialsByIds(materialIds) {
    await delay(150)
    return materialIds.map((id) => MATERIALS[id]).filter((m): m is Material => Boolean(m))
  },
}

export const courseService = mockCourseService
