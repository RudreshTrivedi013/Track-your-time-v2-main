import { authApi } from '@/api/auth'
import { hardLogout, isAuthError, useAuthStore } from '@/stores/authStore'
import { useWsStore } from '@/stores/wsStore'
import { initServiceWorker, unregisterServiceWorker } from '@/lib/sw-registration'
import { useQueryClient } from '@tanstack/react-query'
import { parseApiError } from '@/lib/utils'
import type { TokenResponse, User } from '@/types/api'
import toast from 'react-hot-toast'

export function useAuth() {
  const { setAuth, clearAuth } = useAuthStore()
  const { socket } = useWsStore()
  const queryClient = useQueryClient()

  /**
   * Store the tokens, then try to hydrate the user.
   *
   * The /auth/me call is deliberately NON-FATAL. The credentials were already
   * accepted and the tokens are already persisted, so a transient failure here
   * must not surface as "login failed" — that used to leave the user staring
   * at an error while actually being authenticated.
   *
   * Callers must therefore treat `isAuthenticated === true` with `user === null`
   * as a legal, transient state.
   */
  const finishAuth = async (tokens: TokenResponse): Promise<User | null> => {
    localStorage.setItem('refresh_token', tokens.refresh_token)
    localStorage.setItem('refresh_token_at', String(Date.now()))
    useAuthStore.getState().setAccessToken(tokens.access_token)

    let user: User | null = null
    try {
      user = await authApi.me()
      setAuth(tokens.access_token, user)
    } catch (err) {
      if (isAuthError(err)) {
        await hardLogout({ navigate: false })
        throw err
      }
      console.warn('[Auth] /auth/me unreachable after sign-in — continuing', err)
    }

    // Register the worker only — deliberately do NOT prompt here. By this
    // point we are several awaits past the form submit, so the click's user
    // activation has expired and requestPermission() would silently resolve to
    // 'default' without ever showing the browser prompt. Asking is left to the
    // banner and to the post-save prompt in TaskFormSheet, both of which call
    // it straight from a click.
    initServiceWorker().catch(console.error)
    return user
  }

  const login = async (email: string, password: string) =>
    finishAuth(await authApi.login({ email, password }))

  const signup = async (email: string, password: string, timezone: string) =>
    finishAuth(await authApi.signup({ email, password, timezone }))

  const logout = async () => {
    const refreshToken = localStorage.getItem('refresh_token')
    try {
      if (refreshToken) await authApi.logout(refreshToken)
    } catch (err) {
      console.warn('Logout API call failed:', parseApiError(err))
    }
    socket?.close()
    await unregisterServiceWorker()
    queryClient.clear()
    clearAuth()
    toast.success('Signed out successfully')
  }

  return { login, signup, logout }
}
