import api from './axios'
import type { LoginRequest, SignupRequest, TokenResponse, User, UserUpdate } from '@/types/api'

export const authApi = {
  signup: (data: SignupRequest) =>
    api.post<TokenResponse>('/auth/signup', data).then((r) => r.data),

  login: (data: LoginRequest) =>
    api.post<TokenResponse>('/auth/login', data).then((r) => r.data),

  logout: (refreshToken: string) =>
    api.post('/auth/logout', { refresh_token: refreshToken }),

  refresh: (refreshToken: string) =>
    api.post<TokenResponse>('/auth/refresh', { refresh_token: refreshToken }).then((r) => r.data),

  me: () => api.get<User>('/auth/me').then((r) => r.data),

  updateMe: (data: UserUpdate) => api.patch<User>('/auth/me', data).then((r) => r.data),
}
