import { useState } from 'react'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Button } from '@/components/ui/button'
import { Clock } from '@/lib/icons'

interface SnoozePopoverProps {
  onSnooze: (minutes: number) => void
  disabled?: boolean
}

const SNOOZE_OPTIONS = [
  { label: '10 minutes', value: 10 },
  { label: '30 minutes', value: 30 },
  { label: '1 hour', value: 60 },
  { label: '4 hours', value: 240 },
  { label: 'Tomorrow', value: 60 * 24 },
]

/**
 * Fixed presets only. The old version had a free-text "custom minutes" number
 * input, which is a keyboard, a parse and a validation path for something
 * nobody needs precision on.
 */
export function SnoozePopover({ onSnooze, disabled }: SnoozePopoverProps) {
  const [open, setOpen] = useState(false)

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="secondary" size="sm" disabled={disabled}>
          <Clock className="size-3.5" />
          Snooze
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-48 p-1">
        {SNOOZE_OPTIONS.map((opt) => (
          <button
            key={opt.label}
            type="button"
            onClick={() => {
              onSnooze(opt.value)
              setOpen(false)
            }}
            className="flex min-h-[44px] w-full items-center rounded-lg px-3 text-sm text-text-secondary transition-colors hover:bg-white/5 hover:text-text-primary"
          >
            {opt.label}
          </button>
        ))}
      </PopoverContent>
    </Popover>
  )
}
