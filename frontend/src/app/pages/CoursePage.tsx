import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { CourseHeader } from '@/features/courses/CourseHeader'
import { UnitAccordion } from '@/features/courses/UnitAccordion'
import { RecentMaterialsGrid } from '@/features/courses/RecentMaterialsGrid'
import { Skeleton } from '@/components/ui/Skeleton'
import { courseService } from '@/services/courseService'
import { progressService } from '@/services/progressService'
import { MATERIALS } from '@/mocks/courseData'
import { APP_CONFIG } from '@/config/app.config'
import type { Course } from '@/types/course'

export function CoursePage() {
  const { courseSlug } = useParams<{ courseSlug: string }>()
  const navigate = useNavigate()
  const [course, setCourse] = useState<Course | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    if (!courseSlug) return
    setIsLoading(true)
    courseService.getCourseBySlug(courseSlug).then((c) => {
      setCourse(c)
      setNotFound(!c)
      setIsLoading(false)
      if (c) document.title = `${c.name} · ${APP_CONFIG.productName}`
    })
  }, [courseSlug])

  const progress = progressService.getProgress()
  const recentMaterials = Object.values(MATERIALS).slice(0, 6)

  if (isLoading) {
    return (
      <div className="mx-auto max-w-5xl space-y-6 px-4 py-6 md:px-8 md:py-8">
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (notFound || !course) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-16 text-center">
        <h1 className="text-lg font-semibold text-ink-900">Curso no encontrado</h1>
        <p className="mt-2 text-sm text-ink-500">Este piloto solo incluye el curso Historia Crítica del Perú.</p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-4 py-6 md:px-8 md:py-8">
      <CourseHeader
        course={course}
        progressPercent={progress.overallPercent}
        onStartSession={() => navigate(`/cursos/${course.slug}/estudiar`)}
      />

      <section>
        <h2 className="mb-3 text-sm font-semibold text-ink-900">Unidades y semanas</h2>
        <div className="space-y-3">
          {course.units.map((unit, i) => (
            <UnitAccordion key={unit.id} unit={unit} index={i} courseSlug={course.slug} />
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-ink-900">Materiales recientes</h2>
        <RecentMaterialsGrid materials={recentMaterials} />
      </section>
    </div>
  )
}
