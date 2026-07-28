import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { companionApi } from '@/api/companion'
import { ACTIVITIES_KEY } from '@/hooks/useActivities'
import type { ProductivityStatus } from '@/types/companion'
import type { ReminderActivity } from '@/types/api'
import { Button } from '@/components/ui/button'
import { VoiceNoteInput } from '@/components/ui/VoiceNoteInput'
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
 * Edits an hourly check-in entry from the activity timeline — whether it
 * was already answered or missed entirely. There is no cutoff: a slot from
 * five (or fifty) hours ago is exactly as editable as one from a minute
 * ago, because the backend endpoint enforces none either.
 */

const STATUS_OPTIONS: { value: ProductivityStatus; label: string }[] = [
  { value: 'focused', label: 'Productive' },
  { value: 'idle', label: 'Average' },
  { value: 'distracted', label: 'Distracted' },
]

interface EditCheckinSheetProps {
  activity: ReminderActivity | null
  onClose: () => void
}

export function EditCheckinSheet({ activity, onClose }: EditCheckinSheetProps) {
  const queryClient = useQueryClient()
  const open = activity !== null

  const [status, setStatus] = useState<ProductivityStatus | null>(null)
  const [note, setNote] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!activity) return
    const currentStatus = activity.metadata?.status as string | undefined
    setStatus(currentStatus === 'focused' || currentStatus === 'idle' || currentStatus === 'distracted' ? currentStatus : null)
    setNote(activity.optional_notes ?? '')
  }, [activity])

  const handleSave = async () => {
    if (!activity || !status || submitting) return
    setSubmitting(true)
    try {
      await companionApi.updateCheckinActivity(activity.id, {
        status,
        note: note.trim() || null,
      })
      queryClient.invalidateQueries({ queryKey: ACTIVITIES_KEY })
      toast.success('Check-in updated')
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
          <DrawerTitle>Edit check-in</DrawerTitle>
          <DrawerDescription>
            {activity ? `From ${formatTime(activity.timestamp)}` : ''}
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

          <VoiceNoteInput
            value={note}
            onChange={setNote}
            placeholder="Add a note (optional)"
            disabled={submitting}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSave()
            }}
          />

          <div className="flex gap-2">
            <Button type="button" variant="secondary" className="flex-1" onClick={onClose} disabled={submitting}>
              Cancel
            </Button>
            <Button type="button" className="flex-1" onClick={handleSave} disabled={!status || submitting}>
              {submitting ? <Loader2 className="size-4 animate-spin" /> : 'Save'}
            </Button>
          </div>
        </div>
      </DrawerContent>
    </Drawer>
  )
}
