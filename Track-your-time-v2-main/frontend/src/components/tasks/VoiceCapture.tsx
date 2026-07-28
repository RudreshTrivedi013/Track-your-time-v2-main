import { useState } from 'react'
import toast from 'react-hot-toast'
import { voiceApi } from '@/api/voice'
import { useVoiceInput } from '@/hooks/useVoiceInput'
import { Button } from '@/components/ui/button'
import { Loader2, Mic, X } from '@/lib/icons'
import { cn, parseApiError } from '@/lib/utils'
import type { ParsedTask } from '@/types/api'

/**
 * Dictate a reminder instead of typing it.
 *
 * Lives inside the create sheet rather than on its own page: speaking is a way
 * to fill this form, not a separate feature. The old implementation was a
 * dedicated /voice route plus a 280-line confirmation dialog that could create
 * several tasks at once — this fills the fields you can already see, so what
 * you review before saving is the same form either way.
 *
 * Speech recognition runs in the browser; only the resulting text is sent to
 * the backend for parsing.
 */

export interface VoiceDraft {
  title: string
  /** ISO string, or null when the parser couldn't pin down a time. */
  dueAt: string | null
  recurrence: ParsedTask['recurrence']
  intervalMinutes: number | null
  notes: string[]
}

/** Combine the parser's separate date and time fields into one ISO instant. */
function toIso(dueDate: string | null, dueTime: string | null): string | null {
  if (!dueDate) return null
  const [y, m, d] = dueDate.split('-').map(Number)
  if (!y || !m || !d) return null
  const [hh, mm] = (dueTime ?? '09:00').split(':').map(Number)
  const local = new Date(y, m - 1, d, hh || 0, mm || 0, 0, 0)
  return Number.isNaN(local.getTime()) ? null : local.toISOString()
}

interface VoiceCaptureProps {
  onDraft: (draft: VoiceDraft) => void
  disabled?: boolean
}

export function VoiceCapture({ onDraft, disabled }: VoiceCaptureProps) {
  const {
    isSupported,
    isRecording,
    transcript,
    interimTranscript,
    error,
    startRecording,
    stopRecording,
    resetTranscript,
  } = useVoiceInput()
  const [parsing, setParsing] = useState(false)

  // Firefox and others have no Web Speech API — hide rather than offer a
  // button that cannot work.
  if (!isSupported) return null

  const spoken = `${transcript}${interimTranscript ? ` ${interimTranscript}` : ''}`.trim()

  const handleParse = async () => {
    const text = transcript.trim()
    if (!text) return
    setParsing(true)
    try {
      const result = await voiceApi.parseTranscript(text)
      const first = result.tasks[0]
      if (!first) {
        toast.error("Couldn't find a task in that")
        return
      }
      onDraft({
        title: first.title,
        dueAt: toIso(first.due_date, first.due_time),
        recurrence: first.recurrence,
        intervalMinutes: first.interval_minutes,
        notes: first.notes.map((n) => n.text),
      })
      resetTranscript()

      if (result.tasks.length > 1) {
        toast(`Heard ${result.tasks.length} tasks — filled in the first one.`)
      }
      // The parser flags anything it guessed at; the fields are on screen and
      // editable, so point at them rather than blocking with a confirm step.
      if (first.ambiguous_fields.length > 0) {
        toast('Check the date and time below.')
      }
    } catch (err) {
      toast.error(parseApiError(err))
    } finally {
      setParsing(false)
    }
  }

  return (
    <div className="space-y-2 rounded-xl border border-border bg-white/[0.02] p-3">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={isRecording ? stopRecording : startRecording}
          disabled={disabled || parsing}
          aria-label={isRecording ? 'Stop recording' : 'Dictate a reminder'}
          aria-pressed={isRecording}
          className={cn(
            'flex size-11 shrink-0 items-center justify-center rounded-full border transition-colors',
            isRecording
              ? 'border-danger bg-danger text-white'
              : 'border-border bg-white/5 text-text-secondary hover:bg-white/10 hover:text-text-primary',
            (disabled || parsing) && 'opacity-50',
          )}
        >
          <Mic className="size-4" />
        </button>

        <p className="min-w-0 flex-1 text-xs text-text-secondary">
          {isRecording
            ? interimTranscript || transcript || 'Listening…'
            : spoken || 'Or say it: “Call the dentist tomorrow at 3pm”'}
        </p>

        {spoken && !isRecording && (
          <button
            type="button"
            onClick={resetTranscript}
            aria-label="Clear transcript"
            className="shrink-0 p-1 text-text-muted hover:text-text-primary"
          >
            <X className="size-4" />
          </button>
        )}
      </div>

      {error && <p className="text-xs text-danger">{error}</p>}

      {transcript.trim() && !isRecording && (
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="w-full"
          onClick={handleParse}
          disabled={parsing}
        >
          {parsing ? <Loader2 className="size-3.5 animate-spin" /> : 'Use this'}
        </Button>
      )}
    </div>
  )
}
