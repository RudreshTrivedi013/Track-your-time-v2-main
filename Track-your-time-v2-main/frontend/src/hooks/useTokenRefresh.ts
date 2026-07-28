import { useEffect, useRef, useCallback } from 'react'
import { useAuthStore, getTokenExpiry } from '@/stores/authStore'
import { refreshAccessToken } from '@/api/axios'

/**
 * How many seconds before token expiry should we proactively refresh.
 * 2 minutes gives a comfortable window even if the browser delays the timer.
 */
const REFRESH_BUFFER_SECONDS = 120

/**
 * Proactive token refresh hook.
 *
 * Prevents auto-logout on inactive tabs by:
 * 1. Scheduling a timer to refresh the access token 2 minutes before it expires.
 * 2. Listening for the `visibilitychange` event so that when a user returns to
 *    an inactive tab, we immediately check and refresh an expired/near-expiry token.
 *
 * Uses the shared `refreshAccessToken()` from axios.ts which has a single-flight
 * lock, so concurrent calls from the 401 interceptor or WebSocket reconnect
 * are safely deduplicated.
 */
export function useTokenRefresh() {
  const { accessToken, isAuthenticated } = useAuthStore()
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const scheduleRefresh = useCallback(
    (token: string) => {
      clearTimer()

      const exp = getTokenExpiry(token)
      if (!exp) return

      const nowSec = Date.now() / 1000
      const delayMs = Math.max((exp - REFRESH_BUFFER_SECONDS - nowSec) * 1000, 0)

      console.debug(
        `[TokenRefresh] Scheduled proactive refresh in ${Math.round(delayMs / 1000)}s (token expires at ${new Date(exp * 1000).toLocaleTimeString()})`,
      )

      if (delayMs === 0) {
        refreshAccessToken()
          .then(() => {
            const freshToken = useAuthStore.getState().accessToken
            if (freshToken) scheduleRefresh(freshToken)
          })
          .catch(() => {
            console.warn('[TokenRefresh] Proactive refresh on mount failed')
          })
        return
      }

      timerRef.current = setTimeout(async () => {
        // Re-check auth state — user may have logged out while timer was pending.
        if (!useAuthStore.getState().isAuthenticated) return

        try {
          await refreshAccessToken()
          // After a successful refresh, schedule the next one using the new token.
          const freshToken = useAuthStore.getState().accessToken
          if (freshToken) scheduleRefresh(freshToken)
        } catch {
          // refreshAccessToken handles the error; the 401 interceptor will
          // kick in on the next API call if this silently failed.
          console.warn('[TokenRefresh] Proactive refresh failed — will retry on next API call')
        }
      }, delayMs)
    },
    [clearTimer],
  )

  // Schedule / reschedule whenever the access token changes.
  useEffect(() => {
    if (!isAuthenticated || !accessToken) {
      clearTimer()
      return
    }

    scheduleRefresh(accessToken)

    return () => clearTimer()
  }, [isAuthenticated, accessToken, scheduleRefresh, clearTimer])

  // Handle tab becoming visible again — the timer may not have fired if the
  // browser throttled it while the tab was in the background.
  useEffect(() => {
    if (!isAuthenticated) return

    const handleVisibilityChange = async () => {
      if (document.visibilityState !== 'visible') return

      const token = useAuthStore.getState().accessToken
      if (!token || !useAuthStore.getState().isAuthenticated) return

      const exp = getTokenExpiry(token)
      const nowSec = Date.now() / 1000

      // If the token is already expired or will expire within the buffer, refresh now.
      if (exp && exp - nowSec < REFRESH_BUFFER_SECONDS) {
        console.debug('[TokenRefresh] Tab became visible with near-expiry token — refreshing now')
        try {
          await refreshAccessToken()
          const freshToken = useAuthStore.getState().accessToken
          if (freshToken) scheduleRefresh(freshToken)
        } catch {
          console.warn('[TokenRefresh] Visibility refresh failed')
        }
      } else if (token) {
        // Token is still valid, but reschedule the timer since the old timer
        // may have been throttled/cleared by the browser.
        scheduleRefresh(token)
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange)
  }, [isAuthenticated, scheduleRefresh])
}
