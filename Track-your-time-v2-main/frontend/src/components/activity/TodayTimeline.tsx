import { useState } from 'react'
import { format } from 'date-fns'
import { useActivities } from '@/hooks/useActivities'
import type { ActivityType, ReminderActivity } from '@/types/api'
import { EditCheckinSheet } from './EditCheckinSheet'
import { Check, ChevronDown, Clock, Plus, Pencil } from '@/lib/icons'
import { cn } from '@/lib/utils'

/**
 * Collapsed-by-default activity log on Home.
 *
 * Two changes from the original:
 *  - Layout was a fixed 4-column grid (`4.25rem 2rem 1.1fr 1fr`) that had no
 *    responsive behaviour and squeezed the task title to nothing at 375px.
 *    Now a single flex row: icon, title + label, time on the right.
 *  - The icon map pulled 14 distinct lucide icons for a secondary panel.
 *    Four is enough to distinguish the categories that matter.
 */

type Meta = { label: string; icon: typeof Plus; tone: string }

const NEUTRAL = 'text-text-secondary bg-white/5'
const OK = 'text-success bg-success/10'
const WARN = 'text-warning bg-warning/10'

const ACTIVITY_META: Record<ActivityType, Meta> = {
  created: { label: 'Created', icon: Plus, tone: NEUTRAL },
  started: { label: 'Started', icon: Clock, tone: NEUTRAL },
  working: { label: 'Working', icon: Clock, tone: NEUTRAL },
  updated: { label: 'Updated', icon: Pencil, tone: NEUTRAL },
  completed: { label: 'Completed', icon: Check, tone: OK },
  blocked: { label: 'Muted', icon: Clock, tone: NEUTRAL },
  resumed: { label: 'Reopened', icon: Clock, tone: NEUTRAL },
  snoozed: { label: 'Snoozed', icon: Clock, tone: WARN },
  deleted: { label: 'Deleted', icon: Pencil, tone: NEUTRAL },
  reminder_response: { label: 'Response', icon: Pencil, tone: NEUTRAL },
  hourly_checkin: { label: 'Check-in', icon: Clock, tone: NEUTRAL },
  voice_update: { label: 'Update', icon: Pencil, tone: NEUTRAL },
  text_update: { label: 'Update', icon: Pencil, tone: NEUTRAL },
  companion_action: { label: 'Update', icon: Pencil, tone: NEUTRAL },
  status_update: { label: 'Update', icon: Pencil, tone: NEUTRAL },
}

const CHECKIN_LABELS: Record<string, Meta> = {
  focused: { label: 'Productive', icon: Check, tone: OK },
  distracted: { label: 'Distracted', icon: Clock, tone: WARN },
  idle: { label: 'Average', icon: Clock, tone: NEUTRAL },
  missed: { label: 'Missed check-in', icon: Clock, tone: NEUTRAL },
}

function displayMeta(activity: ReminderActivity): Meta {
  if (activity.activity_type === 'hourly_checkin') {
    const status = activity.metadata?.status as string | undefined
    return (status && CHECKIN_LABELS[status]) || ACTIVITY_META.hourly_checkin
  }
  return ACTIVITY_META[activity.activity_type] ?? ACTIVITY_META.status_update
}

function TimelineRow({ activity, onEdit }: { activity: ReminderActivity; onEdit?: (a: ReminderActivity) => void }) {
  const meta = displayMeta(activity)
  const Icon = meta.icon
  // Editable regardless of status (given or missed) and regardless of age —
  // the backend enforces no cutoff, so neither does this button.
  const editable = activity.activity_type === 'hourly_checkin' && onEdit

  return (
    <li 
      className={cn(
        "group flex items-start gap-3 border-t border-border/60 py-3 first:border-t-0",
        editable && "cursor-pointer transition-colors hover:bg-white/[0.02]"
      )}
      onClick={() => {
        if (editable && onEdit) {
          onEdit(activity)
        }
      }}
    >
      <span className={`mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg ${meta.tone}`}>
        <Icon size={14} />
      </span>

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm text-text-primary">{activity.task_title}</p>
        <p className="text-xs text-text-muted">{meta.label}</p>
        {activity.optional_notes && (
          <p className="mt-0.5 line-clamp-2 text-xs text-text-secondary">{activity.optional_notes}</p>
        )}
      </div>

      <span className="shrink-0 text-xs tabular-nums text-text-muted">
        {format(new Date(activity.timestamp), 'HH:mm')}
      </span>

      {editable && (
        <button
          type="button"
          aria-label="Edit check-in"
          className="shrink-0 rounded-lg p-1.5 text-text-muted transition-colors group-hover:bg-white/5 group-hover:text-text-primary"
        >
          <Pencil size={14} />
        </button>
      )}
    </li>
  )
}

export function TodayTimeline() {
  const { data: activities = [], isLoading, error } = useActivities({ today: true, limit: 25 })
  const [taskActivityOpen, setTaskActivityOpen] = useState(false)
  const [editingActivity, setEditingActivity] = useState<ReminderActivity | null>(null)

  if (isLoading) {
    return (
      <div className="space-y-2">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-12 animate-pulse rounded-lg bg-white/[0.04]" />
        ))}
      </div>
    )
  }

  if (error) {
    return <p className="text-sm text-danger">Couldn't load today's activity.</p>
  }

  if (activities.length === 0) {
    return <p className="text-sm text-text-secondary">Nothing yet today.</p>
  }

  // Section 1: the user's own hourly check-ins ("what are you working on
  // right now?" answers) — the entries someone actually came here to see.
  // Section 2: everything else (created/completed/snoozed/etc.) — task
  // lifecycle noise, tucked behind a dropdown instead of interleaved.
  const hourlyActivities = activities.filter((a) => a.activity_type === 'hourly_checkin')
  const taskActivities = activities.filter((a) => a.activity_type !== 'hourly_checkin')

  return (
    <div>
      {hourlyActivities.length > 0 ? (
        <ul>
          {hourlyActivities.map((activity) => (
            <TimelineRow key={activity.id} activity={activity} onEdit={setEditingActivity} />
          ))}
        </ul>
      ) : (
        <p className="py-2 text-sm text-text-secondary">No hourly check-ins yet today.</p>
      )}

      {taskActivities.length > 0 && (
        <div className="mt-1 border-t border-border/60">
          <button
            type="button"
            onClick={() => setTaskActivityOpen((v) => !v)}
            className="flex w-full items-center justify-between py-3 text-sm text-text-secondary"
          >
            <span>Task activity ({taskActivities.length})</span>
            <ChevronDown
              size={16}
              className={cn('transition-transform', taskActivityOpen && 'rotate-180')}
            />
          </button>

          {taskActivityOpen && (
            <ul>
              {taskActivities.map((activity) => (
                <TimelineRow key={activity.id} activity={activity} />
              ))}
            </ul>
          )}
        </div>
      )}

      <EditCheckinSheet activity={editingActivity} onClose={() => setEditingActivity(null)} />
    </div>
  )
}
