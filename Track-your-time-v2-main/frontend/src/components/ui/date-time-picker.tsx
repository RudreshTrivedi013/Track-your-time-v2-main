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
 * different (and mostly bad) control on every platform.
 *
 * UX is a two-step inline flow (not a popover — see note below):
 *   Step 1 "Date" — calendar is shown. Tapping a day automatically advances
 *                   to Step 2.
 *   Step 2 "Time" — time dropdown + "Done" button. User can tap the Date tab
 *                   to go back and change the day.
 *
 * WHY INLINE: This component lives inside TaskFormSheet (a vaul Drawer).
 * Both Popover and a nested Drawer were tested and broke in different ways:
 *   - Both render into a document.body portal, outside any hidden wrapper, so
 *     two calendars appeared simultaneously.
 *   - A nested vaul Drawer fights the parent for scroll-lock / drag-dismiss.
 * Inline has no portal, no nesting, no z-index contest.
 *
 * Value is an ISO string (or null), matching the API — callers never juggle
 * Date ↔ string themselves.
 */

const TIME_STEP_MINUTES = 15

const QUICK_CHIPS: { label: string; build: () => Date }[] = [
  { label: 'Today 6pm', build: () => setMinutes(setHours(startOfToday(), 18), 0) },
  { label: 'Tomorrow 9am', build: () => setMinutes(setHours(addDays(startOfToday(), 1), 9), 0) },
  { label: 'This weekend', build: () => setMinutes(setHours(nextSaturday(startOfToday()), 10), 0) },
]

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

function defaultTimeValue(): string {
  const now = new Date()
  const rounded = Math.ceil(now.getMinutes() / TIME_STEP_MINUTES) * TIME_STEP_MINUTES
  return format(
    new Date(now.getFullYear(), now.getMonth(), now.getDate(), now.getHours(), 0).getTime() +
      rounded * 60_000,
    'HH:mm',
  )
}

function combine(day: Date, hhmm: string): Date {
  const [h, m] = hhmm.split(':').map(Number)
  return setMinutes(setHours(startOfDay(day), h), m)
}

type Step = 'date' | 'time'

interface DateTimePickerProps {
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
  const [step, setStep] = useState<Step>('date')

  const selected = value ? new Date(value) : null
  const timeOptions = useTimeOptions()

  const [day, setDay] = useState<Date | undefined>(selected ?? undefined)
  const [time, setTime] = useState<string>(
    selected ? format(selected, 'HH:mm') : defaultTimeValue(),
  )

  // Keep draft in sync when value changes externally (quick chips, clear, voice).
  useEffect(() => {
    if (!value) {
      setDay(undefined)
      return
    }
    const next = new Date(value)
    setDay(next)
    setTime(format(next, 'HH:mm'))
  }, [value])

  const handleOpen = () => {
    setStep('date')
    setExpanded(true)
  }

  const handleClose = () => setExpanded(false)

  const isChipActive = (target: Date) =>
    selected != null && selected.getTime() === target.getTime()

  return (
    <div className="space-y-2.5 relative">
      {/* ── Quick-pick chips ──────────────────────────────────── */}
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

      {/* ── Trigger row ───────────────────────────────────────── */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={disabled}
          onClick={expanded ? handleClose : handleOpen}
          aria-expanded={expanded}
          className={cn(
            'flex min-h-[44px] flex-1 items-center gap-2 rounded-xl border border-border bg-bg-elevated px-3.5',
            'text-left text-base transition-colors hover:border-white/30 disabled:opacity-50',
            selected ? 'text-foreground' : 'text-text-muted',
          )}
        >
          <Clock className="size-4 shrink-0 text-text-muted" />
          <span className="flex-1 truncate">
            {selected ? formatDueDate(value) : placeholder}
          </span>
          <ChevronDown
            className={cn(
              'size-4 shrink-0 text-text-muted transition-transform duration-200',
              expanded && 'rotate-180',
            )}
          />
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

      {/* ── Two-step popup panel ─────────────────────────────── */}
      {expanded && (
        <div className="absolute top-full left-0 right-0 z-50 mt-2 rounded-2xl border border-border bg-bg-elevated overflow-hidden shadow-2xl">

          {/* Tab bar */}
          <div className="flex border-b border-border">
            <StepTab
              label="Date"
              sub={day ? format(day, 'MMM d') : 'Pick a day'}
              active={step === 'date'}
              onClick={() => setStep('date')}
            />
            <StepTab
              label="Time"
              sub={day ? format(combine(day, time), 'h:mm a') : '—'}
              active={step === 'time'}
              disabled={!day}
              onClick={() => { if (day) setStep('time') }}
            />
          </div>

          {/* Step 1 — Calendar */}
          {step === 'date' && (
            <div className="flex justify-center p-3">
              <Calendar
                mode="single"
                selected={day}
                onSelect={(next) => {
                  if (!next) return
                  setDay(next)
                  onChange(combine(next, time).toISOString())
                  // Auto-advance to time — same as every modern calendar app.
                  setStep('time')
                }}
                disabled={{ before: startOfToday() }}
                defaultMonth={day ?? new Date()}
              />
            </div>
          )}

          {/* Step 2 — Time + Done */}
          {step === 'time' && (
            <div className="space-y-4 p-4">
              <p className="text-sm font-medium text-text-secondary">
                {day ? format(day, 'EEEE, MMMM d') : ''}
              </p>

              <Select
                value={time}
                onValueChange={(next) => {
                  setTime(next)
                  onChange(combine(day ?? startOfToday(), next).toISOString())
                  if (!day) setDay(startOfToday())
                }}
              >
                <SelectTrigger aria-label="Time" className="h-12 text-base">
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

              <Button
                type="button"
                className="w-full"
                onClick={handleClose}
              >
                Done
              </Button>
            </div>
          )}
        </div>
      )}

      {selected && selected.getTime() < Date.now() && (
        <p className="text-xs text-warning">That time has already passed.</p>
      )}
    </div>
  )
}

// ── Internal tab component ──────────────────────────────────────────────────

interface StepTabProps {
  label: string
  sub: string
  active: boolean
  disabled?: boolean
  onClick: () => void
}

function StepTab({ label, sub, active, disabled, onClick }: StepTabProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'flex flex-1 flex-col items-center gap-0.5 py-3 text-center transition-colors',
        'border-b-2',
        active
          ? 'border-white text-white'
          : disabled
          ? 'border-transparent text-text-muted cursor-not-allowed'
          : 'border-transparent text-text-secondary hover:text-text-primary',
      )}
    >
      <span className="text-xs font-semibold uppercase tracking-wider">{label}</span>
      <span className={cn('text-xs', active ? 'text-text-secondary' : 'text-text-muted')}>
        {sub}
      </span>
    </button>
  )
}
