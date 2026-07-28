import api from './axios'
import type { DaySummary, SummaryHistoryOut } from '@/types/api'

export const summaryApi = {
  trigger: () => api.post<DaySummary>('/summary/trigger').then((r) => r.data),
  getHistory: (limit = 30, offset = 0) => 
    api.get<SummaryHistoryOut>('/summary/history', { params: { limit, offset } }).then(r => r.data),
}
