import { useState } from 'react'
import type { Task } from '@/types/api'
import { TaskCard } from './TaskCard'
import { ChevronDown } from '@/lib/icons'
import { cn } from '@/lib/utils'

/**
 * Three sections, down from five.
 *
 * `in_progress` and `blocked` fold into Active — the first because the UI no
 * longer has a Start button and the scheduler never distinguished it, the
 * second because a muted task is still an open task, just a quiet one (sorted
 * last so it doesn't crowd things that still need doing).
 */

interface TaskListProps {
  tasks: Task[]
  onCreate?: () => void
}

const dueTime = (t: Task) => (t.due_at ? new Date(t.due_at).getTime() : Number.MAX_SAFE_INTEGER)

export function TaskList({ tasks, onCreate }: TaskListProps) {
  const [doneExpanded, setDoneExpanded] = useState(false)

  const active = tasks
    .filter((t) => t.status === 'pending' || t.status === 'in_progress' || t.status === 'blocked')
    .sort((a, b) => {
      // Muted tasks sink to the bottom; everything else by soonest due.
      const aMuted = a.status === 'blocked' ? 1 : 0
      const bMuted = b.status === 'blocked' ? 1 : 0
      return aMuted - bMuted || dueTime(a) - dueTime(b)
    })
  const snoozed = tasks.filter((t) => t.status === 'snoozed').sort((a, b) => dueTime(a) - dueTime(b))
  const done = tasks.filter((t) => t.status === 'done')

  if (tasks.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-border p-10 text-center">
        <h3 className="text-base font-semibold text-text-primary">Nothing scheduled</h3>
        <p className="mx-auto mt-1 max-w-xs text-sm text-text-secondary">
          Add a reminder and set a time — we'll notify you when it's due.
        </p>
        {onCreate && (
          <button
            type="button"
            onClick={onCreate}
            className="mt-5 min-h-[44px] rounded-xl bg-white px-4 text-sm font-medium text-bg"
          >
            New reminder
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {active.length > 0 && (
        <Section>
          {active.map((task) => (
            <TaskCard key={task.id} task={task} />
          ))}
        </Section>
      )}

      {snoozed.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-xs font-medium text-text-muted">Snoozed</h2>
          <Section>
            {snoozed.map((task) => (
              <TaskCard key={task.id} task={task} />
            ))}
          </Section>
        </div>
      )}

      {done.length > 0 && (
        <div className="space-y-2">
          <button
            type="button"
            onClick={() => setDoneExpanded((v) => !v)}
            className="flex min-h-[44px] items-center gap-1.5 text-xs font-medium text-text-muted transition-colors hover:text-text-secondary"
          >
            <ChevronDown className={cn('size-3.5 transition-transform', doneExpanded && 'rotate-180')} />
            Completed ({done.length})
          </button>
          {doneExpanded && (
            <Section>
              {done.map((task) => (
                <TaskCard key={task.id} task={task} />
              ))}
            </Section>
          )}
        </div>
      )}
    </div>
  )
}

function Section({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-1 gap-3 md:grid-cols-2">{children}</div>
}
