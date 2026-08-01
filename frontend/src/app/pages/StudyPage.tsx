import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { StudyShell } from '@/features/study/StudyShell'
import { LoadingIndicator } from '@/components/feedback/LoadingIndicator'
import { courseService } from '@/services/courseService'
import { APP_CONFIG } from '@/config/app.config'
import type { Course } from '@/types/course'

export function StudyPage() {
  const { courseSlug } = useParams<{ courseSlug: string }>()
  const [course, setCourse] = useState<Course | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (!courseSlug) return
    courseService.getCourseBySlug(courseSlug).then((c) => {
      setCourse(c)
      setIsLoading(false)
      if (c) document.title = `Sala de estudio · ${c.name} · ${APP_CONFIG.productName}`
    })
  }, [courseSlug])

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-surface-100">
        <LoadingIndicator label="Preparando la sala de estudio…" />
      </div>
    )
  }

  if (!course) {
    return (
      <div className="flex h-screen items-center justify-center bg-surface-100 px-6 text-center">
        <p className="text-sm text-ink-500">Curso no encontrado.</p>
      </div>
    )
  }

  return <StudyShell course={course} />
}
