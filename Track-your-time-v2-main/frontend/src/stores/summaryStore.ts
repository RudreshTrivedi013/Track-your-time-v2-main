/**
 * Summary store — holds a pending DaySummary that was received via push
 * notification or WebSocket event so the SummaryPage can display it
 * immediately when the user taps the notification and opens the app.
 */
import { create } from 'zustand'
import type { DaySummary } from '@/types/api'

interface SummaryState {
  pendingSummary: DaySummary | null
  setPendingSummary: (s: DaySummary) => void
  clearPendingSummary: () => void
}

export const useSummaryStore = create<SummaryState>((set) => ({
  pendingSummary: null,
  setPendingSummary: (s) => set({ pendingSummary: s }),
  clearPendingSummary: () => set({ pendingSummary: null }),
}))
