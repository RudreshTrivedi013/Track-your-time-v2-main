import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { companionApi } from '@/api/companion'
import { ACTIVITIES_KEY } from '@/hooks/useActivities'
import { CHECKIN_REMINDERS_KEY } from '@/hooks/useCheckinReminders'
import type { ProductivityStatus } from '@/types/companion'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
} from '@/components/ui/drawer'
import { Loader2 } from '@/lib/icons'
import { cn, formatTime, parseApiError } from '@/lib/utils'

/**
 * Replaces HourlyReminderPanel (1021 lines, a 2-step wizard with four
 * sub-modes, ~20 useState hooks, embedded voice parsing, task creation, a task
 * picker and two stacked modals).
 *
 * A check-in asks one question. It should be one screen, three buttons and a
 * note field — answerable in about two seconds, because that is all the
 * attention a mid-work interruption deserves.
 *
 * All four entry paths into this sheet are unchanged and still handled in
 * Layout.tsx: the useCheckinPanelStore, the ?checkin=1&reminderId= URL params,
 * the service worker's OPEN_CHECKIN_PANEL message, and the legacy /dashboard
 * redirect for service workers already installed on real devices.
 */

const STATUS_OPTIONS: { value: ProductivityStatus; label: string }[] = [
  { value: 'focused', label: 'Productive' },
  { value: 'idle', label: 'Average' },
  { value: 'distracted', label: 'Distracted' },
]

interface CheckinSheetProps {
  open: boolean
  reminderId?: string
  onClose: () => void
}

export function CheckinSheet({ open, reminderId, onClose }: CheckinSheetProps) {
  const queryClient = useQueryClient()

  const [status, setStatus] = useState<ProductivityStatus | null>(null)
  const [note, setNote] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [scheduledFor, setScheduledFor] = useState<string | null>(null)

  // Reset whenever the sheet is reopened for a different reminder.
  useEffect(() => {
    if (!open) return
    setStatus(null)
    setNote('')
    setScheduledFor(null)
  }, [open, reminderId])

  // Purely to title the sheet "Missed reminder from 3:00 PM". Failure is
  // silent — a cosmetic subtitle must never block logging a check-in.
  useEffect(() => {
    if (!open || !reminderId) return
    let cancelled = false
    companionApi
      .getCheckinReminder(reminderId)
      .then((r) => {
        if (!cancelled) setScheduledFor(r.scheduled_time)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [open, reminderId])

  const handleSave = async () => {
    if (!status || submitting) return
    setSubmitting(true)
    const now = new Date()
    try {
      await companionApi.createCheckin({
        status,
        start_at: new Date(now.getTime() - 3_600_000).toISOString(),
        end_at: now.toISOString(),
        note: note.trim() || null,
        reminder_id: reminderId ?? null,
      })
      queryClient.invalidateQueries({ queryKey: CHECKIN_REMINDERS_KEY })
      queryClient.invalidateQueries({ queryKey: ACTIVITIES_KEY })
      toast.success('Check-in saved')
      onClose()
    } catch (err) {
      toast.error(parseApiError(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Drawer open={open} onOpenChange={(next) => !next && onClose()}>
      <DrawerContent>
        <DrawerHeader>
          <DrawerTitle>How's it going?</DrawerTitle>
          <DrawerDescription>
            {scheduledFor
              ? `Missed reminder from ${formatTime(scheduledFor)}`
              : 'Log how the last hour went.'}
          </DrawerDescription>
        </DrawerHeader>

        <div className="space-y-4 px-4 pb-4">
          <div className="space-y-2">
            {STATUS_OPTIONS.map((option) => {
              const active = status === option.value
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setStatus(option.value)}
                  aria-pressed={active}
                  className={cn(
                    'flex w-full min-h-[52px] items-center rounded-xl border px-4 text-sm font-medium transition-colors',
                    active
                      ? 'border-white bg-white text-bg'
                      : 'border-border bg-white/5 text-text-primary hover:bg-white/10',
                  )}
                >
                  {option.label}
                </button>
              )
            })}
          </div>

          <Input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Add a note (optional)"
            disabled={submitting}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSave()
            }}
          />

          <div className="flex gap-2">
            <Button
              type="button"
              variant="secondary"
              className="flex-1"
              onClick={onClose}
              disabled={submitting}
            >
              Not now
            </Button>
            <Button
              type="button"
              className="flex-1"
              onClick={handleSave}
              disabled={!status || submitting}
            >
              {submitting ? <Loader2 className="size-4 animate-spin" /> : 'Save'}
            </Button>
          </div>
        </div>
      </DrawerContent>
    </Drawer>
  )
}
