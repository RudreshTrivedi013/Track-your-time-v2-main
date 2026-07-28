import { useEffect, useMemo, useState } from 'react'
import {
  addDays,
  format,
  nextSaturday,
  setHours,
  setMinutes,
  startOfDay,
  startOfToday,
} from 'date-fns'
import { Calendar } from './calendar'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './select'
import { Button } from './button'
import { ChevronDown, Clock, X } from '@/lib/icons'
import { cn, formatDueDate } from '@/lib/utils'

/**
 * Replacement for `<input type="datetime-local">`, which renders as a
 * different (and mostly bad) control on every platform and is especially
 * awkward on mobile.
 *
 * One-tap presets come first: most reminders are "later today" or "tomorrow
 * morning" and should never require opening a calendar at all. The calendar is
 * the fallback, not the main path.
 *
 * The calendar expands INLINE rather than in a popover or sheet. This
 * component lives inside TaskFormSheet, which is itself a vaul Drawer, and
 * both alternatives were actively broken there:
 *
 *  - Rendering a Drawer and a Popover and switching with `md:hidden` did not
 *    work at all, because each renders into a portal on document.body — well
 *    outside the hidden wrapper — so BOTH opened and two calendars stacked on
 *    screen at once.
 *  - A nested vaul Drawer additionally fights the parent over scroll locking,
 *    focus trapping and drag-to-dismiss.
 *
 * Inline has no portal, no nesting, no z-index contest, and behaves the same
 * on phone and desktop.
 *
 * Value is an ISO string (or null), matching what the API expects, so callers
 * never do their own Date <-> string juggling.
 */

const TIME_STEP_MINUTES = 15

const QUICK_CHIPS: { label: string; build: () => Date }[] = [
  { label: 'Today 6pm', build: () => setMinutes(setHours(startOfToday(), 18), 0) },
  { label: 'Tomorrow 9am', build: () => setMinutes(setHours(addDays(startOfToday(), 1), 9), 0) },
  { label: 'This weekend', build: () => setMinutes(setHours(nextSaturday(startOfToday()), 10), 0) },
]

/** ["00:00", "00:15", …] as {value,label} pairs. */
function useTimeOptions() {
  return useMemo(() => {
    const base = startOfToday()
    const slots: { value: string; label: string }[] = []
    for (let minutes = 0; minutes < 24 * 60; minutes += TIME_STEP_MINUTES) {
      const d = new Date(base.getTime() + minutes * 60_000)
      slots.push({ value: format(d, 'HH:mm'), label: format(d, 'h:mm a') })
    }
    return slots
  }, [])
}

/** Nearest upcoming slot, so the time list opens somewhere sensible. */
function defaultTimeValue(): string {
  const now = new Date()
  const rounded = Math.ceil(now.getMinutes() / TIME_STEP_MINUTES) * TIME_STEP_MINUTES
  return format(new Date(now.getFullYear(), now.getMonth(), now.getDate(), now.getHours(), 0)
    .getTime() + rounded * 60_000, 'HH:mm')
}

function combine(day: Date, hhmm: string): Date {
  const [h, m] = hhmm.split(':').map(Number)
  return setMinutes(setHours(startOfDay(day), h), m)
}

interface DateTimePickerProps {
  /** ISO string, or null for "no due date". */
  value: string | null
  onChange: (value: string | null) => void
  disabled?: boolean
  placeholder?: string
}

export function DateTimePicker({
  value,
  onChange,
  disabled,
  placeholder = 'Add a due date',
}: DateTimePickerProps) {
  const [expanded, setExpanded] = useState(false)
  const selected = value ? new Date(value) : null
  const timeOptions = useTimeOptions()

  const [day, setDay] = useState<Date | undefined>(selected ?? undefined)
  const [time, setTime] = useState<string>(selected ? format(selected, 'HH:mm') : defaultTimeValue())

  // Keep the draft in step when the value changes from outside — the quick
  // chips, the clear button, or voice dictation filling the form.
  useEffect(() => {
    if (!value) {
      setDay(undefined)
      return
    }
    const next = new Date(value)
    setDay(next)
    setTime(format(next, 'HH:mm'))
  }, [value])

  const isChipActive = (target: Date) => selected != null && selected.getTime() === target.getTime()

  return (
    <div className="space-y-2.5">
      <div className="flex flex-wrap gap-2">
        {QUICK_CHIPS.map((chip) => {
          const target = chip.build()
          const active = isChipActive(target)
          return (
            <button
              key={chip.label}
              type="button"
              disabled={disabled}
              onClick={() => {
                onChange(target.toISOString())
                setExpanded(false)
              }}
              className={cn(
                'min-h-[40px] rounded-full border px-3.5 text-xs font-medium transition-colors',
                active
                  ? 'border-white bg-white text-bg'
                  : 'border-border bg-white/5 text-text-secondary hover:bg-white/10 hover:text-text-primary',
                disabled && 'opacity-50',
              )}
            >
              {chip.label}
            </button>
          )
        })}
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={disabled}
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          className={cn(
            'flex min-h-[44px] flex-1 items-center gap-2 rounded-xl border border-border bg-bg-elevated px-3.5',
            'text-left text-base transition-colors hover:border-white/30 disabled:opacity-50',
            selected ? 'text-foreground' : 'text-text-muted',
          )}
        >
          <Clock className="size-4 shrink-0 text-text-muted" />
          <span className="flex-1 truncate">{selected ? formatDueDate(value) : placeholder}</span>
          <ChevronDown className={cn('size-4 shrink-0 text-text-muted transition-transform', expanded && 'rotate-180')} />
        </button>

        {selected && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Clear due date"
            disabled={disabled}
            onClick={() => {
              onChange(null)
              setExpanded(false)
            }}
          >
            <X className="size-4" />
          </Button>
        )}
      </div>

      {expanded && (
        <div className="space-y-4 rounded-xl border border-border bg-bg-elevated p-3">
          <div className="flex justify-center">
            <Calendar
              mode="single"
              selected={day}
              onSelect={(next) => {
                if (!next) return
                setDay(next)
                onChange(combine(next, time).toISOString())
              }}
              // A reminder in the past can never fire.
              disabled={{ before: startOfToday() }}
              defaultMonth={day ?? new Date()}
            />
          </div>

          <div className="space-y-1.5">
            <span className="text-xs font-medium text-text-secondary">Time</span>
            <Select
              value={time}
              onValueChange={(next) => {
                setTime(next)
                onChange(combine(day ?? startOfToday(), next).toISOString())
                if (!day) setDay(startOfToday())
              }}
            >
              <SelectTrigger aria-label="Time">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {timeOptions.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <Button type="button" variant="secondary" className="w-full" onClick={() => setExpanded(false)}>
            Done
          </Button>
        </div>
      )}

      {selected && selected.getTime() < Date.now() && (
        <p className="text-xs text-warning">That time has already passed.</p>
      )}
    </div>
  )
}
