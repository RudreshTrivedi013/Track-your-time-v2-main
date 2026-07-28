import { api } from './axios'
import type { ParsedVoiceResult } from '@/types/api'

export const voiceApi = {
  /**
   * Turn a spoken sentence into a structured task draft.
   * Parses only — never persists. The caller reviews and edits before POST /tasks.
   */
  parseTranscript: async (transcript: string): Promise<ParsedVoiceResult> => {
    const { data } = await api.post<ParsedVoiceResult>('/tasks/parse-voice', { transcript })
    return data
  },
}
