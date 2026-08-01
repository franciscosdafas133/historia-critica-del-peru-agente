/**
 * Traduce un topicId (id interno de navegación, ej. 't-transiciones-demograficas')
 * al título legible del tema, para construir la pregunta en lenguaje natural que
 * el backend necesita en los modos que generan contenido sobre un tema sin que
 * el estudiante haya escrito nada (practicar, evaluar, repasar).
 *
 * Vive aquí, no en StudyService, para no ampliar el contrato del servicio:
 * httpStudyService resuelve el título internamente a partir del topicId ya
 * recibido, usando la misma fuente (PILOT_COURSE) que ya usa mockCourseService.
 */
import { PILOT_COURSE } from '@/mocks/courseData'

function topicTitle(topicId: string | null): string | null {
  if (!topicId) return null
  for (const unit of PILOT_COURSE.units) {
    for (const week of unit.weeks) {
      const topic = week.topics.find((t) => t.id === topicId)
      if (topic) return topic.title
    }
  }
  return null
}

export function practiceTopicPrompt(topicId: string | null): string {
  const title = topicTitle(topicId)
  return title ? `Genera una pregunta de práctica sobre: ${title}` : 'Genera una pregunta de práctica sobre el curso en general'
}

export function assessTopicPrompt(topicId: string | null): string {
  const title = topicTitle(topicId)
  return title
    ? `Genera una pregunta de microevaluación sobre: ${title}`
    : 'Genera una pregunta de microevaluación sobre el curso en general'
}

export function reviewTopicPrompt(topicId: string | null): string {
  const title = topicTitle(topicId)
  return title ? `Genera una tarjeta de repaso sobre: ${title}` : 'Genera una tarjeta de repaso sobre el curso en general'
}
