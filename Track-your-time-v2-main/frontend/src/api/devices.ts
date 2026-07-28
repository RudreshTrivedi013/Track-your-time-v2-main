import api from './axios'
import type { Device } from '@/types/api'

export const devicesApi = {
  register: (pushToken: string, isPrimary = true) =>
    api.post<Device>('/devices', { push_token: pushToken, is_primary: isPrimary }).then((r) => r.data),

  list: () => api.get<Device[]>('/devices').then((r) => r.data),

  ping: (id: string) => api.post(`/devices/${id}/ping`),

  testPush: () => api.post('/devices/test-push').then(r => r.data),
}
