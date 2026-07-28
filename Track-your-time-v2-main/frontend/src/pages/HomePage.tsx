import { useState } from 'react'
import { format } from 'date-fns'
import { useTasks } from '@/hooks/useTasks'
import { useAuthStore } from '@/stores/authStore'
import { TaskList } from '@/components/tasks/TaskList'
import { TaskFormSheet } from '@/components/tasks/TaskFormSheet'
import { TodayTimeline } from '@/components/activity/TodayTimeline'
import { Button } from '@/components/ui/button'
import { ChevronDown, Plus } from '@/lib/icons'
import { cn } from '@/lib/utils'

/**
 * The merged Dashboard + Tasks screen.
 *
 * Those were two routes rendering the identical <TaskList> over the same
 * unfiltered useTasks(), so the tab bar offered a choice with no difference
 * behind it.
 *
 * The three stat tiles (Pending / In Progress / Completed) are gone: on a
 * phone they pushed the actual list below the fold to tell you three numbers
 * you can see by looking at it — and one of them counted a status the UI no
 * longer has.
 */
export default function HomePage() {
  const { data: tasks = [], isLoading, error } = useTasks()
  const { user } = useAuthStore()
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [timelineOpen, setTimelineOpen] = useState(false)

  // Just the name, title-cased — no "Hello,". Emails give us lowercase local
  // parts (and often a dot/underscore separator), so capitalise each word.
  const name = user?.email
    ?.split('@')[0]
    .split(/[._-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')

  return (
    <div className="space-y-5">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold tracking-tight text-text-primary">
            {name ?? ''}
          </h1>
          <p className="text-xs text-text-secondary">{format(new Date(), 'EEEE, d MMMM')}</p>
        </div>

        {/* On mobile this is the FAB in Layout; here it's for pointer users. */}
        <Button className="hidden md:inline-flex" onClick={() => setIsCreateOpen(true)}>
          <Plus className="size-4" />
          New reminder
        </Button>
      </header>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-28 animate-pulse rounded-2xl border border-border bg-bg-surface" />
          ))}
        </div>
      ) : error ? (
        <div className="rounded-2xl border border-danger/20 bg-danger/5 p-4 text-sm text-danger">
          Couldn't load your reminders. Check your connection and try again.
        </div>
      ) : (
        <TaskList tasks={tasks} onCreate={() => setIsCreateOpen(true)} />
      )}

      {/* Secondary information — collapsed by default so it never competes
          with the list for attention on a small screen. */}
      <div className="space-y-2 border-t border-border pt-4">
        <button
          type="button"
          onClick={() => setTimelineOpen((v) => !v)}
          className="flex min-h-[44px] items-center gap-1.5 text-xs font-medium text-text-muted transition-colors hover:text-text-secondary"
        >
          <ChevronDown className={cn('size-3.5 transition-transform', timelineOpen && 'rotate-180')} />
          Today's activity
        </button>
        {timelineOpen && <TodayTimeline />}
      </div>

      <TaskFormSheet open={isCreateOpen} onClose={() => setIsCreateOpen(false)} />
    </div>
  )
}
