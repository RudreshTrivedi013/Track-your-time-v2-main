import { useEffect, useRef } from 'react'
import { Mic } from '@/lib/icons'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { useVoiceInput } from '@/hooks/useVoiceInput'

interface VoiceNoteInputProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  disabled?: boolean
  onKeyDown?: (e: React.KeyboardEvent<HTMLInputElement>) => void
}

/**
 * Input with an inline mic button that uses the existing `useVoiceInput` hook
 * (Web Speech API). All SpeechRecognition types are properly defined in the
 * hook — no any-casts needed here.
 *
 * - While recording: shows interim (in-progress) text as a live preview inside
 *   the input; input becomes read-only so typing doesn't conflict.
 * - When recording stops: the confirmed transcript is appended to the note
 *   value and the hook is reset for the next session.
 * - On unsupported browsers (Firefox): mic button is simply not rendered.
 * - Mic access errors ("Blocked", "No speech") surface as a small error line
 *   below the input instead of failing silently.
 */
export function VoiceNoteInput({
  value,
  onChange,
  placeholder,
  disabled,
  onKeyDown,
}: VoiceNoteInputProps) {
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

  // Keep a ref so the effect always reads the latest `value` without
  // needing it as a dependency (avoids stale-closure append bugs).
  const valueRef = useRef(value)
  useEffect(() => {
    valueRef.current = value
  }, [value])

  // Append the final transcript to the note when recording stops.
  const wasRecording = useRef(false)
  useEffect(() => {
    if (wasRecording.current && !isRecording && transcript) {
      const base = valueRef.current
      onChange(base ? `${base} ${transcript}` : transcript)
      resetTranscript()
    }
    wasRecording.current = isRecording
  }, [isRecording, transcript, onChange, resetTranscript])

  const toggle = () => (isRecording ? stopRecording() : startRecording())

  // Show the live interim text inside the field while recording so the user
  // can see recognition in progress.
  const displayValue =
    isRecording && interimTranscript
      ? value
        ? `${value} ${interimTranscript}`
        : interimTranscript
      : value

  return (
    <div className="space-y-1">
      <div className="relative flex items-center">
        <Input
          value={displayValue}
          onChange={(e) => {
            // Block typed edits while recording to avoid conflicts.
            if (!isRecording) onChange(e.target.value)
          }}
          placeholder={isRecording ? 'Listening…' : placeholder}
          disabled={disabled}
          onKeyDown={onKeyDown}
          // Suppress the cursor while recording so it's clear the field is driven by voice.
          readOnly={isRecording}
          className={cn(
            isSupported && 'pr-10',
            isRecording && 'border-red-400/50 focus-visible:ring-red-400/30',
          )}
        />
        {isSupported && (
          <button
            type="button"
            onClick={toggle}
            disabled={disabled}
            aria-label={isRecording ? 'Stop recording' : 'Dictate note'}
            className={cn(
              'absolute right-3 rounded-md p-0.5 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-white/50',
              isRecording
                ? 'text-red-400 animate-pulse'
                : 'text-text-secondary hover:text-text-primary',
            )}
          >
            <Mic className="size-4" />
          </button>
        )}
      </div>
      {error && (
        <p className="px-1 text-xs text-red-400">{error}</p>
      )}
    </div>
  )
}
