/**
 * Device store — holds the ID of the device registered with the backend.
 *
 * Populated by sw-registration.ts after a successful POST /devices.
 * Consumed by Layout.tsx to know which device ID to ping every 5 minutes.
 */
import { create } from 'zustand'

interface DeviceState {
  deviceId: string | null
  setDeviceId: (id: string) => void
  clearDevice: () => void
}

export const useDeviceStore = create<DeviceState>((set) => ({
  deviceId: null,
  setDeviceId: (id) => set({ deviceId: id }),
  clearDevice: () => set({ deviceId: null }),
}))
