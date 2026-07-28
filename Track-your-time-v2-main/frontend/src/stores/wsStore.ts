import { create } from 'zustand'

type WsStatus = 'disconnected' | 'connecting' | 'connected' | 'reconnecting'

interface WsState {
  socket: WebSocket | null
  status: WsStatus
  setSocket: (socket: WebSocket | null) => void
  setStatus: (status: WsStatus) => void
}

export const useWsStore = create<WsState>((set) => ({
  socket: null,
  status: 'disconnected',
  setSocket: (socket) => set({ socket }),
  setStatus: (status) => set({ status }),
}))
