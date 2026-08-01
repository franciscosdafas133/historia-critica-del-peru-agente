import { Link } from 'react-router-dom'
import { AlertCircle } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import type { Topic } from '@/types/course'

export function NeedsReviewCard({ topics, courseSlug }: { topics: Topic[]; courseSlug: string }) {
  if (topics.length === 0) return null

  return (
    <Card>
      <h2 className="mb-3 flex items-center gap-1.5 text-sm font-semibold text-ink-900">
        <AlertCircle className="h-4 w-4 text-attention-500" aria-hidden="true" />
        Temas que necesitan refuerzo
      </h2>
      <ul className="space-y-2">
        {topics.map((topic) => (
          <li key={topic.id}>
            <Link
              to={`/cursos/${courseSlug}/estudiar`}
              className="flex items-center justify-between rounded-lg bg-attention-50 px-3 py-2.5 text-sm text-attention-700 transition-colors duration-150 hover:bg-attention-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-attention-500"
            >
              {topic.title}
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  )
}
