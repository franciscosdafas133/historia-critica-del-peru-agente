import { Link, useNavigate } from 'react-router-dom'
import { BookOpen, FileText, ArrowRight } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { ProgressBar } from '@/components/ui/ProgressBar'
import type { Course } from '@/types/course'
import type { ProgressSummary } from '@/types/study'

interface ActiveCourseCardProps {
  course: Course
  progress: ProgressSummary
  lastTopicTitle: string | null
}

export function ActiveCourseCard({ course, progress, lastTopicTitle }: ActiveCourseCardProps) {
  const navigate = useNavigate()

  return (
    <Card hoverable padded={false} className="overflow-hidden">
      <Link to={`/cursos/${course.slug}`} className="block focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500 rounded-xl">
        <div className="h-2 bg-gradient-to-r from-brand-500 to-tutor-500" aria-hidden="true" />
        <div className="p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-brand-600">Curso activo</p>
              <h2 className="mt-1 text-lg font-semibold text-ink-900">{course.name}</h2>
              <p className="mt-0.5 text-sm text-ink-500">Prof. {course.professor}</p>
            </div>
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
              <BookOpen className="h-5 w-5" aria-hidden="true" />
            </span>
          </div>

          <div className="mt-4 flex items-center gap-1.5 text-xs text-ink-500">
            <FileText className="h-3.5 w-3.5" aria-hidden="true" />
            {course.totalMaterials} materiales disponibles
          </div>

          <div className="mt-4">
            <ProgressBar percent={progress.overallPercent} label="Progreso general" />
          </div>

          {lastTopicTitle && (
            <p className="mt-3 text-xs text-ink-500">
              Último tema: <span className="font-medium text-ink-700">{lastTopicTitle}</span>
            </p>
          )}
        </div>
      </Link>

      <div className="border-t border-surface-200 px-5 py-3.5">
        <Button
          size="sm"
          icon={<ArrowRight className="h-4 w-4" />}
          iconPosition="right"
          onClick={() => navigate(`/cursos/${course.slug}/estudiar`)}
        >
          Continuar estudiando
        </Button>
      </div>
    </Card>
  )
}
