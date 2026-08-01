import { useEffect, useState } from 'react'
import { GreetingHeader } from '@/features/dashboard/GreetingHeader'
import { WeekSummaryCard } from '@/features/dashboard/WeekSummaryCard'
import { ActiveCourseCard } from '@/features/dashboard/ActiveCourseCard'
import { NextActivityCard } from '@/features/dashboard/NextActivityCard'
import { NeedsReviewCard } from '@/features/dashboard/NeedsReviewCard'
import { RecentActivityCard } from '@/features/dashboard/RecentActivityCard'
import { Skeleton } from '@/components/ui/Skeleton'
import { courseService } from '@/services/courseService'
import { progressService } from '@/services/progressService'
import { MOCK_STUDENT } from '@/mocks/studentData'
import { APP_CONFIG } from '@/config/app.config'
import type { Course, Topic } from '@/types/course'

export function DashboardPage() {
  const [course, setCourse] = useState<Course | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    document.title = `Inicio · ${APP_CONFIG.productName}`
    courseService.getCourseBySlug(APP_CONFIG.pilotCourseSlug).then((c) => {
      setCourse(c)
      setIsLoading(false)
    })
  }, [])

  const progress = progressService.getProgress()
  const activity = progressService.getRecentActivity()

  const allTopics: Topic[] = course?.units.flatMap((u) => u.weeks.flatMap((w) => w.topics)) ?? []
  const needsReviewTopics = allTopics.filter((t) => t.status === 'needs_review')
  const lastTopic = allTopics.find((t) => t.id === progress.lastTopicId)

  if (isLoading || !course) {
    return (
      <div className="mx-auto max-w-5xl space-y-6 px-4 py-6 md:px-8 md:py-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-56 w-full" />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-4 py-6 md:px-8 md:py-8">
      <GreetingHeader firstName={MOCK_STUDENT.firstName} />

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        <ActiveCourseCard course={course} progress={progress} lastTopicTitle={lastTopic?.title ?? null} />
        <div className="space-y-5">
          <WeekSummaryCard progress={progress} />
          <NextActivityCard />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        <NeedsReviewCard topics={needsReviewTopics} courseSlug={course.slug} />
        <RecentActivityCard activity={activity} />
      </div>
    </div>
  )
}
