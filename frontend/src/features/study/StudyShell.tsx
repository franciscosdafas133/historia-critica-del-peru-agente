import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Menu } from 'lucide-react'
import { StudyLeftPanel } from './StudyLeftPanel'
import { StudyModeSelector } from './StudyModeSelector'
import { EvidenceSidebar } from './EvidenceSidebar'
import { EvidenceFloatingButton } from './EvidenceFloatingButton'
import { UnderstandMode } from './modes/UnderstandMode'
import { SolveMode } from './modes/SolveMode'
import { PracticeMode } from './modes/PracticeMode'
import { AssessMode } from './modes/AssessMode'
import { ReviewMode } from './modes/ReviewMode'
import { DebateMode } from './modes/DebateMode'
import { Drawer } from '@/components/ui/Drawer'
import { EvidencePanel } from '@/features/evidence/EvidencePanel'
import { SourcePreviewModal } from '@/features/evidence/SourcePreviewModal'
import { ThemeToggle } from '@/components/layout/ThemeToggle'
import { IconButton } from '@/components/ui/IconButton'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import { progressService } from '@/services/progressService'
import type { Course, Topic } from '@/types/course'
import type { Evidence, StudyMode } from '@/types/study'

interface StudyShellProps {
  course: Course
}

export function StudyShell({ course }: StudyShellProps) {
  const navigate = useNavigate()
  const isDesktopWithSidebar = useMediaQuery('(min-width: 1024px)')

  const allWeeks = course.units.flatMap((u) => u.weeks)
  const firstWeek = allWeeks.find((w) => !w.isExamWeek)
  const firstTopic = firstWeek?.topics[0] ?? null

  const [currentTopic, setCurrentTopic] = useState<Topic | null>(firstTopic)
  // La semana activa se deriva del tema seleccionado: cada tema pertenece a
  // una única semana en la estructura actual del curso, así que no hace
  // falta un segundo estado independiente que pudiera desincronizarse.
  const currentWeekId = allWeeks.find((w) => w.topics.some((t) => t.id === currentTopic?.id))?.id ?? firstWeek?.id ?? ''
  const [activeMode, setActiveMode] = useState<StudyMode>(() => progressService.getLastMode() ?? 'understand')
  const [collapsed, setCollapsed] = useState(false)
  const [evidence, setEvidence] = useState<Evidence[]>([])
  const [previewEvidence, setPreviewEvidence] = useState<Evidence | null>(null)
  const [isEvidenceDrawerOpen, setIsEvidenceDrawerOpen] = useState(false)
  const [recentActivity, setRecentActivity] = useState(() => progressService.getRecentActivity())
  const [progress, setProgress] = useState(() => progressService.getProgress())

  useEffect(() => {
    progressService.setLastMode(activeMode)
  }, [activeMode])

  useEffect(() => {
    if (currentTopic) {
      progressService.updateProgress({ lastTopicId: currentTopic.id })
    }
  }, [currentTopic])

  function handleSelectTopic(topic: Topic) {
    setCurrentTopic(topic)
    setEvidence([])
  }

  function handleActivity(summary: string) {
    const entry = {
      id: `act-${Date.now()}`,
      courseId: course.id,
      mode: activeMode,
      topicId: currentTopic?.id ?? null,
      summary,
      timestamp: new Date().toISOString(),
    }
    progressService.logActivity(entry)
    setRecentActivity(progressService.getRecentActivity())
    setProgress(progressService.getProgress())
  }

  const modeContent = {
    understand: <UnderstandMode topicId={currentTopic?.id ?? null} onEvidenceUpdate={setEvidence} onActivity={handleActivity} />,
    solve: <SolveMode topicId={currentTopic?.id ?? null} onActivity={handleActivity} />,
    practice: <PracticeMode topicId={currentTopic?.id ?? null} onEvidenceUpdate={setEvidence} onActivity={handleActivity} />,
    assess: <AssessMode courseId={course.id} onActivity={handleActivity} />,
    review: <ReviewMode topicId={currentTopic?.id ?? null} onActivity={handleActivity} />,
    debate: (
      <DebateMode
        topicId={currentTopic?.id ?? null}
        onEvidenceUpdate={setEvidence}
        onActivity={handleActivity}
        onViewSource={setPreviewEvidence}
      />
    ),
  }[activeMode]

  return (
    <div className="flex h-screen overflow-hidden bg-surface-100">
      <StudyLeftPanel
        course={course}
        currentWeekId={currentWeekId}
        currentTopicId={currentTopic?.id ?? null}
        onSelectTopic={handleSelectTopic}
        collapsed={collapsed && isDesktopWithSidebar}
        onToggleCollapsed={() => setCollapsed((c) => !c)}
        recentActivity={recentActivity}
        progressPercent={progress.overallPercent}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-surface-200 bg-surface-50 px-4 py-2.5 md:hidden">
          <IconButton icon={<Menu className="h-4 w-4" />} label="Volver al curso" onClick={() => navigate(`/cursos/${course.slug}`)} />
          <span className="text-sm font-medium text-ink-900">{currentTopic?.title ?? course.name}</span>
          <ThemeToggle />
        </header>

        <div className="border-b border-surface-200 bg-surface-50">
          <StudyModeSelector activeMode={activeMode} onSelectMode={setActiveMode} />
        </div>

        <div className="flex min-h-0 flex-1 flex-col">{modeContent}</div>
      </div>

      <EvidenceSidebar evidence={evidence} onViewSource={setPreviewEvidence} />

      <EvidenceFloatingButton count={evidence.length} onClick={() => setIsEvidenceDrawerOpen(true)} />

      <Drawer isOpen={isEvidenceDrawerOpen} onClose={() => setIsEvidenceDrawerOpen(false)} title="Evidencias">
        <EvidencePanel evidence={evidence} onViewSource={setPreviewEvidence} />
      </Drawer>

      <SourcePreviewModal evidence={previewEvidence} onClose={() => setPreviewEvidence(null)} />
    </div>
  )
}
