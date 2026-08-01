import { GraduationCap, FileText, Calendar } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { ProgressBar } from '@/components/ui/ProgressBar'
import type { Course } from '@/types/course'

interface CourseHeaderProps {
  course: Course
  progressPercent: number
  onStartSession: () => void
}

export function CourseHeader({ course, progressPercent, onStartSession }: CourseHeaderProps) {
  return (
    <div className="rounded-xl border border-surface-300 bg-surface-50 p-6 shadow-soft">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-brand-600">
            {course.code} · Sección {course.section} · {course.period}
          </p>
          <h1 className="mt-1 text-xl font-semibold tracking-tight text-ink-900 md:text-2xl">{course.name}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-500">
            <span className="inline-flex items-center gap-1.5">
              <GraduationCap className="h-4 w-4" aria-hidden="true" /> Prof. {course.professor}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <FileText className="h-4 w-4" aria-hidden="true" /> {course.totalMaterials} materiales
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Calendar className="h-4 w-4" aria-hidden="true" /> {course.credits} créditos
            </span>
          </div>
        </div>

        <Button size="lg" onClick={onStartSession} className="shrink-0">
          Iniciar sesión de estudio
        </Button>
      </div>

      <div className="mt-5 max-w-sm">
        <ProgressBar percent={progressPercent} label="Progreso general del curso" />
      </div>
    </div>
  )
}
