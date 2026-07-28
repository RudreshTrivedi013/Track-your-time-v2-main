import { useEffect, useState } from 'react'
import { useCreateTask, useUpdateTask } from '@/hooks/useTasks'
import { maybePromptForPush } from '@/lib/push-prompt'
import type { Task } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { DateTimePicker } from '@/components/ui/date-time-picker'
import { VoiceCapture, type VoiceDraft } from './VoiceCapture'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from '@/components/ui/drawer'
import { ChevronDown, Loader2, Plus, Trash2 } from '@/lib/icons'
import { cn } from '@/lib/utils'

/**
 * One sheet for both create and edit.
 *
 * Only Title and the due date are visible. Category, recurrence, interval and
 * the checklist live behind "More options" — the old modal showed all seven
 * fields at once, which made adding "call mum at 6" look like filing a form.
 */

type Recurrence = 'none' | 'interval' | 'daily' | 'weekly'

interface TaskFormSheetProps {
  open: boolean
  onClose: () => void
  /** Omit to create. */
  task?: Task
}

export function TaskFormSheet({ open, onClose, task }: TaskFormSheetProps) {
  const isEdit = Boolean(task)
  const createMutation = useCreateTask()
  const updateMutation = useUpdateTask()
  const pending = createMutation.isPending || updateMutation.isPending

  const [title, setTitle] = useState('')
  const [dueAt, setDueAt] = useState<string | null>(null)
  const [category, setCategory] = useState('')
  const [recurrence, setRecurrence] = useState<Recurrence>('none')
  const [intervalMinutes, setIntervalMinutes] = useState('')
  const [notes, setNotes] = useState<string[]>([])
  const [showOptions, setShowOptions] = useState(false)

  // Re-seed whenever the sheet opens (or opens on a different task).
  useEffect(() => {
    if (!open) return
    setTitle(task?.title ?? '')
    setDueAt(task?.due_at ?? null)
    setCategory(task?.category ?? '')
    setRecurrence((task?.recurrence as Recurrence) ?? 'none')
    setIntervalMinutes(task?.interval_minutes ? String(task.interval_minutes) : '')
    setNotes(task?.notes?.map((n) => n.text) ?? [])
    setShowOptions(false)
  }, [open, task])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = title.trim()
    if (!trimmed || pending) return

    const payload = {
      title: trimmed,
      due_at: dueAt,
      recurrence,
      interval_minutes: recurrence === 'interval' ? Number(intervalMinutes) || null : null,
      category: category.trim() || null,
    }

    try {
      if (isEdit && task) {
        await updateMutation.mutateAsync({ id: task.id, data: payload })
      } else {
        await createMutation.mutateAsync({
          ...payload,
          source: 'text' as const,
          notes: notes
            .map((text, i) => ({ text: text.trim(), done: false, order_index: i }))
            .filter((n) => n.text.length > 0),
        })
      }

      // A reminder with a due date is worthless if it can't reach them.
      // Ask at the moment the need becomes concrete, not at signup where the
      // prompt has no context and gets reflexively dismissed.
      if (dueAt) void maybePromptForPush()

      onClose()
    } catch {
      // The mutation hooks already surface the error toast.
    }
  }

  return (
    <Drawer open={open} onOpenChange={(next) => !next && onClose()}>
      <DrawerContent>
        <DrawerHeader>
          <DrawerTitle>{isEdit ? 'Edit reminder' : 'New reminder'}</DrawerTitle>
        </DrawerHeader>

        <form onSubmit={handleSubmit} className="flex min-h-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4">
            {/* Dictation fills the fields below rather than replacing the
                form, so there is one thing to review before saving either
                way. Only offered on create — editing by voice would mean
                deciding what to overwrite. */}
            {!isEdit && (
              <VoiceCapture
                disabled={pending}
                onDraft={(draft: VoiceDraft) => {
                  setTitle(draft.title)
                  setDueAt(draft.dueAt)
                  setRecurrence(draft.recurrence as Recurrence)
                  setIntervalMinutes(draft.intervalMinutes ? String(draft.intervalMinutes) : '')
                  if (draft.notes.length > 0) setNotes(draft.notes)
                  // Reveal the advanced fields if dictation actually set any,
                  // otherwise the user can't see what was filled in.
                  if (draft.recurrence !== 'none' || draft.notes.length > 0) setShowOptions(true)
                }}
              />
            )}

            <div className="space-y-1.5">
              <Label htmlFor="task-title">What do you need to remember?</Label>
              <Input
                id="task-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Call the dentist"
                disabled={pending}
                autoFocus={!isEdit}
              />
            </div>

            <div className="space-y-1.5">
              <Label>When</Label>
              <DateTimePicker value={dueAt} onChange={setDueAt} disabled={pending} />
            </div>

            <button
              type="button"
              onClick={() => setShowOptions((v) => !v)}
              className="flex min-h-[44px] w-full items-center justify-between text-sm text-text-secondary transition-colors hover:text-text-primary"
            >
              More options
              <ChevronDown className={cn('size-4 transition-transform', showOptions && 'rotate-180')} />
            </button>

            {showOptions && (
              <div className="space-y-4 border-t border-border pt-4">
                <div className="space-y-1.5">
                  <Label htmlFor="task-category">Category</Label>
                  <Input
                    id="task-category"
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    placeholder="Work, Personal…"
                    disabled={pending}
                  />
                </div>

                <div className="space-y-1.5">
                  <Label>Repeat</Label>
                  <Select
                    value={recurrence}
                    onValueChange={(v) => setRecurrence(v as Recurrence)}
                    disabled={pending}
                  >
                    <SelectTrigger aria-label="Repeat">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Never</SelectItem>
                      <SelectItem value="daily">Every day</SelectItem>
                      <SelectItem value="weekly">Every week</SelectItem>
                      <SelectItem value="interval">Every N minutes</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {recurrence === 'interval' && (
                  <div className="space-y-1.5">
                    <Label htmlFor="task-interval">Minutes between repeats</Label>
                    <Input
                      id="task-interval"
                      type="number"
                      inputMode="numeric"
                      min={1}
                      value={intervalMinutes}
                      onChange={(e) => setIntervalMinutes(e.target.value)}
                      placeholder="30"
                      disabled={pending}
                    />
                  </div>
                )}

                {!isEdit && (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label>Checklist</Label>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => setNotes((n) => [...n, ''])}
                        disabled={pending}
                      >
                        <Plus className="size-3.5" />
                        Add
                      </Button>
                    </div>
                    {notes.map((note, i) => (
                      <div key={i} className="flex items-center gap-2">
                        <Input
                          value={note}
                          onChange={(e) =>
                            setNotes((prev) => prev.map((v, idx) => (idx === i ? e.target.value : v)))
                          }
                          placeholder="Step…"
                          disabled={pending}
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          aria-label="Remove step"
                          onClick={() => setNotes((prev) => prev.filter((_, idx) => idx !== i))}
                          disabled={pending}
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="flex gap-2 p-4">
            <Button type="button" variant="secondary" className="flex-1" onClick={onClose} disabled={pending}>
              Cancel
            </Button>
            <Button type="submit" className="flex-1" disabled={!title.trim() || pending}>
              {pending ? <Loader2 className="size-4 animate-spin" /> : isEdit ? 'Save' : 'Create'}
            </Button>
          </div>
        </form>
      </DrawerContent>
    </Drawer>
  )
}
