import { useState, useRef, useCallback } from 'react'
import { Mic } from '@/lib/icons'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

interface VoiceNoteInputProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  disabled?: boolean
  onKeyDown?: (e: React.KeyboardEvent<HTMLInputElement>) => void
}

/**
 * Input with an inline mic button that uses the browser's Web Speech API
 * (SpeechRecognition) to transcribe voice into the note field.
 *
 * - Falls back gracefully: if the browser doesn't support SpeechRecognition
 *   (e.g. Firefox without the flag), the mic button is simply not rendered.
 * - Transcription is APPENDED to any existing text so the user can mix
 *   typing and speaking freely.
 * - Uses `interimResults: false` so only the final, committed transcript is
 *   inserted — no flickering mid-word text.
 */
export function VoiceNoteInput({
  value,
  onChange,
  placeholder,
  disabled,
  onKeyDown,
}: VoiceNoteInputProps) {
  const [listening, setListening] = useState(false)
  const recognitionRef = useRef<SpeechRecognition | null>(null)

  const SpeechRecognitionAPI =
    typeof window !== 'undefined'
      ? window.SpeechRecognition ?? (window as typeof window & { webkitSpeechRecognition?: typeof SpeechRecognition }).webkitSpeechRecognition
      : undefined

  const supported = !!SpeechRecognitionAPI

  const toggleListening = useCallback(() => {
    if (!SpeechRecognitionAPI) return

    if (listening) {
      recognitionRef.current?.stop()
      return
    }

    const recognition = new SpeechRecognitionAPI()
    recognition.continuous = false
    recognition.interimResults = false
    recognition.lang = 'en-US'

    recognition.onstart = () => setListening(true)
    recognition.onend = () => setListening(false)
    recognition.onerror = () => setListening(false)

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      const transcript = event.results[0][0].transcript.trim()
      // Append with a space if there's already text
      onChange(value ? `${value} ${transcript}` : transcript)
    }

    recognitionRef.current = recognition
    recognition.start()
  }, [listening, value, onChange, SpeechRecognitionAPI])

  return (
    <div className="relative flex items-center">
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        onKeyDown={onKeyDown}
        // Make room for the mic button so text doesn't overlap it
        className={cn(supported && 'pr-10')}
      />
      {supported && (
        <button
          type="button"
          onClick={toggleListening}
          disabled={disabled}
          aria-label={listening ? 'Stop recording' : 'Dictate note'}
          className={cn(
            'absolute right-3 rounded-md p-0.5 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-white/50',
            listening
              ? 'text-red-400 animate-pulse'
              : 'text-text-secondary hover:text-text-primary',
          )}
        >
          <Mic className="size-4" />
        </button>
      )}
    </div>
  )
}
