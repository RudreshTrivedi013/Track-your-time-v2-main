import { useState } from 'react'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Bell, BellOff, Clock, MoreVertical, Pencil, Trash2 } from '@/lib/icons'

const SNOOZE_OPTIONS = [
  { label: '10 minutes', value: 10 },
  { label: '30 minutes', value: 30 },
  { label: '1 hour', value: 60 },
  { label: '4 hours', value: 240 },
  { label: 'Tomorrow', value: 60 * 24 },
]

interface TaskActionsMenuProps {
  muted: boolean
  disabled?: boolean
  /** Omit to hide the Snooze option entirely (e.g. task is already done). */
  onSnooze?: (minutes: number) => void
  onEdit: () => void
  onToggleMute: () => void
  onDelete: () => void
}

/**
 * The overflow menu behind `⋯`.
 *
 * "Mute" is the `block` action renamed. Blocking was never about blockers —
 * it clears the scheduler cursors and takes the task out of the due query,
 * i.e. it is the only way to stop a reminder nagging without completing it.
 * Calling that "Block" in danger-red made a routine choice look like an error.
 */
export function TaskActionsMenu({
  muted,
  disabled,
  onSnooze,
  onEdit,
  onToggleMute,
  onDelete,
}: TaskActionsMenuProps) {
  const [confirmOpen, setConfirmOpen] = useState(false)

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" aria-label="More actions" disabled={disabled}>
            <MoreVertical className="size-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          {onSnooze && (
            <DropdownMenuSub>
              <DropdownMenuSubTrigger>
                <Clock />
                Snooze
              </DropdownMenuSubTrigger>
              <DropdownMenuSubContent>
                {SNOOZE_OPTIONS.map((opt) => (
                  <DropdownMenuItem key={opt.label} onSelect={() => onSnooze(opt.value)}>
                    {opt.label}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuSubContent>
            </DropdownMenuSub>
          )}
          <DropdownMenuItem onSelect={onEdit}>
            <Pencil />
            Edit
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={onToggleMute}>
            {muted ? <Bell /> : <BellOff />}
            {muted ? 'Unmute' : 'Mute reminders'}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem destructive onSelect={() => setConfirmOpen(true)}>
            <Trash2 />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Not window.confirm(): it is suppressed or rendered as jarring system
          chrome inside an installed PWA, especially on iOS. */}
      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogTitle>Delete this reminder?</AlertDialogTitle>
          <AlertDialogDescription>This can't be undone.</AlertDialogDescription>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={onDelete}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
