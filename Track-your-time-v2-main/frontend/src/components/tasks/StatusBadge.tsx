import type { TaskStatus } from '@/types/api'
import { Badge, type BadgeProps } from '@/components/ui/badge'

/**
 * Five DB statuses, three user-facing ones.
 *
 * `in_progress` renders as Pending because "Start" no longer exists in the UI
 * and the scheduler never treated it differently anyway. `blocked` renders as
 * "Muted" in neutral grey rather than danger red — muting a reminder is a
 * normal choice, not an error state.
 *
 * The TaskStatus enum itself is untouched in the DB and API.
 */
const STATUS_CONFIG: Record<TaskStatus, { label: string; variant: BadgeProps['variant'] } | null> = {
  // Pending is the default state and needs no badge at all — see TaskCard.
  pending: null,
  in_progress: null,
  snoozed: { label: 'Snoozed', variant: 'snoozed' },
  done: { label: 'Done', variant: 'done' },
  blocked: { label: 'Muted', variant: 'neutral' },
}

interface StatusBadgeProps {
  status: TaskStatus
  /** Pending tasks past their due date read as overdue. */
  overdue?: boolean
  className?: string
}

export function StatusBadge({ status, overdue, className }: StatusBadgeProps) {
  if (overdue && (status === 'pending' || status === 'in_progress')) {
    return (
      <Badge variant="overdue" className={className}>
        Overdue
      </Badge>
    )
  }

  const config = STATUS_CONFIG[status]
  if (!config) return null

  return (
    <Badge variant={config.variant} className={className}>
      {config.label}
    </Badge>
  )
}
