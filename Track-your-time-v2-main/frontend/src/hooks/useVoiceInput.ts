import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Thin wrapper over the Web Speech API for dictating a task.
 *
 * Speech recognition runs on-device (or via the browser's own service) and is
 * free; the transcript is then sent to the backend for LLM parsing. Chrome and
 * Edge support this; Firefox does not, so `isSupported` gates the UI rather
 * than the button failing mysteriously.
 *
 * Scope is deliberately narrow: no text-to-speech readback, no multi-task
 * flows. Just "hold the mic, say the thing, get a transcript".
 */

// The Web Speech API is not in TypeScript's DOM lib.
interface SpeechRecognitionAlternativeLike {
  transcript: string
}
interface SpeechRecognitionResultLike {
  isFinal: boolean
  0: SpeechRecognitionAlternativeLike
}
interface SpeechRecognitionEventLike {
  resultIndex: number
  results: { length: number; [index: number]: SpeechRecognitionResultLike }
}
interface SpeechRecognitionLike {
  lang: string
  continuous: boolean
  interimResults: boolean
  start(): void
  stop(): void
  abort(): void
  onresult: ((event: SpeechRecognitionEventLike) => void) | null
  onerror: ((event: { error: string }) => void) | null
  onend: (() => void) | null
}
type SpeechRecognitionCtor = new () => SpeechRecognitionLike

function getRecognitionCtor(): SpeechRecognitionCtor | null {
  if (typeof window === 'undefined') return null
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor
    webkitSpeechRecognition?: SpeechRecognitionCtor
  }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

export function useVoiceInput() {
  const [isRecording, setIsRecording] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [interimTranscript, setInterimTranscript] = useState('')
  const [error, setError] = useState<string | null>(null)

  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)
  const isSupported = getRecognitionCtor() !== null

  // Stop the microphone if the component unmounts mid-recording, otherwise the
  // browser keeps the recording indicator on.
  useEffect(() => {
    return () => {
      recognitionRef.current?.abort()
      recognitionRef.current = null
    }
  }, [])

  const stopRecording = useCallback(() => {
    recognitionRef.current?.stop()
    setIsRecording(false)
  }, [])

  const startRecording = useCallback(() => {
    const Ctor = getRecognitionCtor()
    if (!Ctor) {
      setError('Voice input is not supported in this browser')
      return
    }

    setError(null)
    setInterimTranscript('')

    const recognition = new Ctor()
    recognition.lang = navigator.language || 'en-US'
    recognition.continuous = true
    recognition.interimResults = true

    recognition.onresult = (event) => {
      let finalChunk = ''
      let interim = ''
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i]
        if (result.isFinal) finalChunk += result[0].transcript
        else interim += result[0].transcript
      }
      if (finalChunk) setTranscript((prev) => (prev ? `${prev} ${finalChunk}` : finalChunk).trim())
      setInterimTranscript(interim)
    }

    recognition.onerror = (event) => {
      // 'aborted' is what we get from our own stop()/abort() calls.
      if (event.error === 'aborted') return
      setError(
        event.error === 'not-allowed'
          ? 'Microphone access was blocked'
          : event.error === 'no-speech'
            ? "Didn't catch that — try again"
            : 'Voice input failed',
      )
      setIsRecording(false)
    }

    recognition.onend = () => {
      setIsRecording(false)
      setInterimTranscript('')
    }

    recognitionRef.current = recognition
    recognition.start()
    setIsRecording(true)
  }, [])

  const resetTranscript = useCallback(() => {
    setTranscript('')
    setInterimTranscript('')
    setError(null)
  }, [])

  return {
    isSupported,
    isRecording,
    transcript,
    interimTranscript,
    error,
    startRecording,
    stopRecording,
    resetTranscript,
  }
}
