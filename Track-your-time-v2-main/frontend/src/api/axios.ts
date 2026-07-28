import axios from 'axios'
import { hardLogout, idbGetToken, useAuthStore, isTokenNearExpiry } from '@/stores/authStore'

const envApiUrl = import.meta.env.VITE_API_URL as string | undefined

// VITE_API_URL is baked in at build time, so a missing value is a build/CI
// defect — not something to paper over. The old fallback pointed the SPA at
// its own static host, which made POST /auth/login return index.html and
// surface as an unexplainable "Network Error".
if (!envApiUrl && import.meta.env.PROD) {
  throw new Error('VITE_API_URL is not set — refusing to fall back to window.location.origin')
}

const API_URL = envApiUrl || 'http://localhost:8000'

if (!envApiUrl) {
  console.warn('[API] VITE_API_URL unset — using dev default', API_URL)
}
console.debug('[API] configured baseURL:', API_URL)

export const api = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
})

// Endpoints that authenticate rather than consume authentication. A 401 from
// any of these means "those credentials are wrong" and must be handed straight
// back to the caller — never fed into the refresh-and-retry machinery.
const AUTH_ENDPOINTS = ['/auth/login', '/auth/signup', '/auth/refresh', '/auth/logout']
const isAuthEndpoint = (url: string | undefined): boolean =>
  AUTH_ENDPOINTS.some((path) => (url ?? '').includes(path))

// --- Request interceptor: attach Bearer token ---
api.interceptors.request.use((config) => {
  if (isAuthEndpoint(config.url)) {
    // Actively strip, don't merely skip. axios 1.x flattens
    // defaults.headers.common into config.headers BEFORE interceptors run, so
    // a header set elsewhere would otherwise still ride along on login.
    config.headers.delete?.('Authorization')
    delete (config.headers as unknown as Record<string, unknown>).Authorization
    return config
  }

  const token = useAuthStore.getState().accessToken
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// --- Single-flight refresh, coordinated ACROSS TABS ---
//
// The backend rotates the refresh token on every use and blocklists the old
// one, returning 401 if it is ever replayed. An in-memory promise only
// deduplicates within one tab, but the refresh token lives in localStorage
// which every tab shares — so two tabs waking at once (useTokenRefresh fires
// on visibilitychange, making alt-tab a reliable trigger) would both post the
// same token, and the loser got logged out.
//
// navigator.locks makes the critical section exclusive across tabs. Inside it
// we re-check a freshness stamp: if another tab rotated moments ago we ADOPT
// its result instead of burning our own rotation.
const REFRESH_LOCK = 'smartreminder-refresh'
const REFRESH_STAMP = 'refresh_token_at'
const ADOPT_WINDOW_MS = 60_000 // 60 s — wide enough for slow connections to avoid a race

let refreshPromise: Promise<string> | null = null

const authChannel: BroadcastChannel | null =
  typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel('smartreminder-auth') : null

authChannel?.addEventListener('message', (event: MessageEvent) => {
  if (event.data?.type === 'token' && event.data.accessToken) {
    useAuthStore.setState({ accessToken: event.data.accessToken, isAuthenticated: true })
  }
})

/**
 * Refresh the access token. Returns the new access token, or throws.
 * Safe to call concurrently from anywhere, in any number of tabs.
 */
export async function refreshAccessToken(): Promise<string> {
  if (refreshPromise) return refreshPromise

  // FIRST check: did this tab (or another) just refresh the token successfully?
  // By checking the in-memory state FIRST we bypass the slow IDB entirely
  // and prevent the catastrophic bug where a stale IDB read overwrites a fresh memory state.
  const currentToken = useAuthStore.getState().accessToken
  if (currentToken && !isTokenNearExpiry(currentToken)) {
    return currentToken
  }

  const run = async (): Promise<string> => {
    // Another tab may have rotated while we waited for the lock. Adopt its
    // token rather than replaying ours (which is now blocklisted).
    const stampedAt = Number(localStorage.getItem(REFRESH_STAMP) ?? 0)
    if (Date.now() - stampedAt < ADOPT_WINDOW_MS) {
      const adopted = await idbGetToken()
      if (adopted && !isTokenNearExpiry(adopted)) {
        useAuthStore.getState().setAccessToken(adopted)
        console.debug('[Auth] Adopted a token refreshed by another tab')
        return adopted
      }
    }

    // Read INSIDE the lock. Reading it before acquiring is exactly what let a
    // losing tab post an already-rotated token.
    const refreshToken = localStorage.getItem('refresh_token')
    if (!refreshToken) throw new Error('No refresh token available')

    try {
      const { data } = await axios.post(`${API_URL}/auth/refresh`, { refresh_token: refreshToken })
      const newAccessToken: string = data.access_token
      const newRefreshToken: string | undefined = data.refresh_token

      if (newRefreshToken) localStorage.setItem('refresh_token', newRefreshToken)
      localStorage.setItem(REFRESH_STAMP, String(Date.now()))
      useAuthStore.getState().setAccessToken(newAccessToken)
      authChannel?.postMessage({ type: 'token', accessToken: newAccessToken })

      console.debug('[Auth] Token refreshed')
      return newAccessToken
    } catch (err: any) {
      if (err.response?.status === 401) {
        // If the refresh token ITSELF is expired/invalid, log out immediately.
        // Doing this here rather than only in the response interceptor guarantees
        // we don't get stuck in a WebSocket reconnect loop if it initiated the refresh.
        await hardLogout()
      }
      throw err
    }
  }

  refreshPromise = (
    'locks' in navigator ? navigator.locks.request(REFRESH_LOCK, run) : run()
  ).finally(() => {
    refreshPromise = null
  }) as Promise<string>

  return refreshPromise
}

// --- Response interceptor: handle 401 with automatic token refresh ---
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // Bail out for: non-401s, already-retried requests, and — critically —
    // the auth endpoints themselves. A wrong-password 401 from /auth/login is
    // an answer, not an expired session. Feeding it into the refresh path used
    // to trigger a full page reload that destroyed the error toast the user
    // was meant to read, which is the "login sometimes just flashes" report.
    if (
      error.response?.status !== 401 ||
      originalRequest?._retry ||
      isAuthEndpoint(originalRequest?.url)
    ) {
      return Promise.reject(error)
    }

    if (!localStorage.getItem('refresh_token')) {
      // No refresh token available. Do NOT call hardLogout() — the token may
      // be transiently missing (OS cleared storage, private browsing eviction,
      // race with another tab). Destroying IDB and store state here was a
      // one-way door that turned a recoverable situation into a permanent
      // logout. Just reject and let the caller handle it.
      return Promise.reject(error)
    }

    originalRequest._retry = true

    try {
      // Concurrent 401s all await the same in-flight promise.
      const newAccessToken = await refreshAccessToken()
      originalRequest.headers = originalRequest.headers ?? {}
      originalRequest.headers.Authorization = `Bearer ${newAccessToken}`
      return api(originalRequest)
    } catch (refreshError) {
      // CRITICAL: Only destroy the session on a definitive auth rejection.
      // A network error (no response) means the backend is cold-starting or the
      // user is briefly offline — the refresh token is still perfectly valid.
      // 403 is NOT included — it can come from CORS blocks or WAF rules, not
      // just invalid credentials.
      const status = (refreshError as { response?: { status?: number } })?.response?.status
      if (status === 401) {
        await hardLogout()
      }
      return Promise.reject(refreshError)
    }
  },
)

export default api
