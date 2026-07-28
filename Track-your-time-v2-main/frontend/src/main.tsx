import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import App from './App'
import { idbGetToken, hardLogout, isAuthError, useAuthStore } from './stores/authStore'
import { useSummaryStore } from './stores/summaryStore'
import { authApi } from './api/auth'
import { refreshAccessToken } from './api/axios'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

// Listen for messages from the service worker (e.g. summary_ready push clicks)
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.addEventListener('message', (event) => {
    if (event.data?.type === 'SUMMARY_READY' && event.data.summary) {
      useSummaryStore.getState().setPendingSummary(event.data.summary)
    }

    if (event.data?.type === 'CHECKIN_LOGGED') {
      queryClient.invalidateQueries({ queryKey: ['checkinReminders'] })
    }
  })
}

/**
 * Hydrate auth before rendering so ProtectedRoute doesn't flicker.
 *
 * Two rules this function must never break:
 *  1. It must never prevent the app from rendering. Anything it throws is
 *     caught by initApp(), which renders in a `finally`.
 *  2. It must only destroy the session on a GENUINE credential rejection.
 *     A network error, CORS block, backend cold start or 5xx means "try
 *     again later", not "log the user out".
 */
async function bootstrapAuth() {
  let token = await idbGetToken()

  // IndexedDB can legitimately be empty (fresh profile, cleared storage, or a
  // database we just self-healed) while a valid refresh token still sits in
  // localStorage. Recover the session instead of dumping the user on /login.
  if (!token && localStorage.getItem('refresh_token')) {
    try {
      token = await refreshAccessToken()
    } catch (err) {
      if (isAuthError(err)) await hardLogout({ navigate: false })
    }
  }

  if (!token) return

  useAuthStore.getState().setAccessToken(token)
  try {
    const user = await authApi.me()
    useAuthStore.getState().setAuth(token, user)
  } catch (err) {
    if (isAuthError(err)) {
      await hardLogout({ navigate: false })
    } else {
      // Transient. Keep the tokens; the app stays optimistically authenticated
      // and will hydrate `user` on the next successful request.
      console.warn('[Boot] /auth/me unreachable — keeping session', err)
    }
  }
}

function renderApp() {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
          <Toaster
            position="top-right"
            toastOptions={{
              duration: 3500,
              style: {
                background: '#1a1a24',
                color: '#f1f5f9',
                border: '1px solid #2a2a3a',
                borderRadius: '12px',
                fontSize: '14px',
              },
              success: {
                iconTheme: {
                  primary: '#10b981',
                  secondary: '#1a1a24',
                },
              },
              error: {
                iconTheme: {
                  primary: '#ef4444',
                  secondary: '#1a1a24',
                },
              },
            }}
          />
        </BrowserRouter>
      </QueryClientProvider>
    </React.StrictMode>,
  )
}

async function initApp() {
  try {
    await bootstrapAuth()
  } catch (err) {
    // Swallow, then render anyway. Previously a rejection here (most often a
    // NotFoundError from a poisoned IndexedDB) meant createRoot() never ran
    // and the user got a permanent blank page with no way to recover.
    console.error('[Boot] auth hydration failed — rendering anyway', err)
  } finally {
    renderApp()
  }
}

initApp()
