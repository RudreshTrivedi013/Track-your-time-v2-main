import api from './axios'
import type { DaySummary, SummaryHistoryOut } from '@/types/api'

export const summaryApi = {
  trigger: () => api.post<DaySummary>('/summary/trigger').then((r) => r.data),

  getHistory: (limit = 30, offset = 0) => 
    api.get<SummaryHistoryOut>('/summary/history', { params: { limit, offset } }).then(r => r.data),

  /** Save user edits to an existing summary. */
  updateSummary: (summaryId: string, editedBullets: string[]) =>
    api.patch<DaySummary>(`/summary/${summaryId}`, { edited_bullets: editedBullets }).then(r => r.data),

  /** Revision-style regenerate: refines the user's edit, doesn't replace it. */
  regenerateSummary: (summaryId: string) =>
    api.post<DaySummary>(`/summary/${summaryId}/regenerate`).then(r => r.data),
}
