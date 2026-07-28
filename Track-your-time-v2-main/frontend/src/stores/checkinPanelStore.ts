import { create } from 'zustand'

interface CheckinPanelState {
  isOpen: boolean
  reminderId?: string
  open: (reminderId?: string) => void
  close: () => void
}

export const useCheckinPanelStore = create<CheckinPanelState>((set) => ({
  isOpen: false,
  reminderId: undefined,
  open: (reminderId) => set({ isOpen: true, reminderId }),
  close: () => set({ isOpen: false, reminderId: undefined }),
}))
