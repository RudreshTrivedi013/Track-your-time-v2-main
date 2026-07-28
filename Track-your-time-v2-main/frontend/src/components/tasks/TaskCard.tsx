import { useState } from 'react'
import type { Task } from '@/types/api'
import { useDeleteTask, useTaskAction } from '@/hooks/useTasks'
import { Button } from '@/components/ui/button'
import { TaskActionsMenu } from './TaskActionsMenu'
import { TaskFormSheet } from './TaskFormSheet'
import { Check, RotateCcw } from '@/lib/icons'
import { cn, formatDueDate, formatTime } from '@/lib/utils'

/**
 * Reduced from eight controls (Start, Complete, Snooze, Block, Reopen,
 * Respond, Edit, Delete) to two plus an overflow menu.
 *
 * Removed outright:
 *  - Start — it only set status to in_progress, which the scheduler treats
 *    identically to pending. It changed nothing except a counter.
 *  - Respond — it wrote an activity log row and never touched task status, so
 *    typing "Completed login" showed a green "Completed" toast while the task
 *    stayed Pending. Actively misleading.
 *  - The Mic/Keyboard source indicator — nothing actionable.
 */

interface TaskCardProps {
  task: Task
}

export function TaskCard({ task }: TaskCardProps) {
  const [isEditOpen, setIsEditOpen] = useState(false)
  const actionMutation = useTaskAction()
  const deleteMutation = useDeleteTask()

  const runAction = (action: string, snoozeMins?: number) => {
    actionMutation.mutate({
      id: task.id,
      data: {
        action,
        client_timestamp: new Date().toISOString(),
        snooze_minutes: snoozeMins,
      },
    })
  }

  const isDone = task.status === 'done'
  const isMuted = task.status === 'blocked'
  const isSnoozed = task.status === 'snoozed'
  const isOverdue =
    !isDone && !isMuted && Boolean(task.due_at) && new Date(task.due_at!).getTime() < Date.now()

  // Colour only where it carries meaning. Pending — the default state — gets
  // no accent at all, which is what stops the list looking like a barcode.
  const accent = isDone
    ? 'border-l-success'
    : isOverdue
      ? 'border-l-danger'
      : isSnoozed
        ? 'border-l-warning'
        : isMuted
          ? 'border-l-text-muted'
          : 'border-l-transparent'

  // A short trailing note so state changes are actually VISIBLE.
  //
  // The single-line redesign dropped StatusBadge and the due-date row, which
  // left the coloured 2px left border as the only signal. That meant snoozing
  // or muting a task changed nothing a user could perceive — the action looked
  // like it had silently failed even though it had gone through.
  //
  // Overdue deliberately stays border-only: the red line already says it, and
  // an "Overdue" pill was explicitly not wanted.
  const statusNote = isMuted
    ? 'Muted'
    : isSnoozed && task.snoozed_until
      ? `Snoozed to ${formatTime(task.snoozed_until)}`
      : isSnoozed
        ? 'Snoozed'
        : !isDone && task.due_at
          ? formatDueDate(task.due_at)
          : null

  return (
    <div
      className={cn(
        'flex items-center gap-2 rounded-2xl border border-border border-l-2 bg-bg-surface py-3 pl-4 pr-2',
        accent,
        isDone && 'opacity-60',
      )}
    >
      <h3
        className={cn(
          'min-w-0 flex-1 truncate text-sm font-medium text-text-primary',
          isDone && 'text-text-secondary line-through',
        )}
      >
        {task.title}
      </h3>

      {statusNote && (
        <span
          className={cn(
            'shrink-0 text-xs tabular-nums',
            isSnoozed ? 'text-warning' : 'text-text-muted',
          )}
        >
          {statusNote}
        </span>
      )}

      {/* Icon-only, so the title gets the horizontal space instead of two
          words of button label. aria-label + title keep it accessible and
          discoverable on hover. */}
      <div className="flex shrink-0 items-center gap-0.5">
        {isDone ? (
          <Button
            variant="secondary"
            size="icon"
            aria-label="Reopen task"
            title="Reopen"
            onClick={() => runAction('reopen')}
            disabled={actionMutation.isPending}
          >
            <RotateCcw className="size-4" />
          </Button>
        ) : (
          <Button
            size="icon"
            aria-label="Mark as done"
            title="Done"
            onClick={() => runAction('done')}
            disabled={actionMutation.isPending}
          >
            <Check className="size-4" />
          </Button>
        )}

        <TaskActionsMenu
          muted={isMuted}
          disabled={actionMutation.isPending || deleteMutation.isPending}
          onSnooze={isDone ? undefined : (mins) => runAction('snooze', mins)}
          onEdit={() => setIsEditOpen(true)}
          onToggleMute={() => runAction(isMuted ? 'reopen' : 'block')}
          onDelete={() => deleteMutation.mutate(task.id)}
        />
      </div>

      <TaskFormSheet open={isEditOpen} onClose={() => setIsEditOpen(false)} task={task} />
    </div>
  )
}
