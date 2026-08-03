/// <reference lib="webworker" />
import { precacheAndRoute, createHandlerBoundToURL } from 'workbox-precaching'
import { NavigationRoute, registerRoute } from 'workbox-routing'

/**
 * Service worker: push handling, notification actions, and an app-shell
 * precache.
 *
 * This file used to live at public/sw.js. Files in public/ are copied
 * verbatim, so `import.meta.env` substitution was impossible there and the
 * API host had to be hardcoded:
 *
 *   const apiBaseUrl = self.location.hostname === 'localhost'
 *     ? 'http://localhost:8000'
 *     : 'https://smartreminder-production-9096.up.railway.app'
 *
 * which silently posted to the wrong backend from any Vercel preview, staging
 * domain, LAN IP used for phone testing, or 127.0.0.1. Compiling the worker
 * through Vite (vite-plugin-pwa, strategies: 'injectManifest') fixes that and
 * gives us the fetch handler Chromium wants before it will offer to install.
 */

declare const self: ServiceWorkerGlobalScope & {
  __WB_MANIFEST: Array<{ url: string; revision: string | null }>
}

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) || self.location.origin

// Precache the built app shell, then serve index.html for navigations so the
// app opens offline instead of showing the browser's error page.
precacheAndRoute(self.__WB_MANIFEST)
registerRoute(new NavigationRoute(createHandlerBoundToURL('/index.html')))

// Notification icons must be PNG — Android renders SVG unreliably here.
const ICON = '/icons/pwa-192.png'
const BADGE = '/icons/pwa-64.png'

// ── Auth storage, shared with the main thread ───────────────────────────────
// KEEP IN SYNC with src/stores/authStore.ts.
// The upgrade handler is mandatory: without it this worker could create
// 'smartreminder-db' at v1 with zero object stores, after which the app's own
// open() never triggered an upgrade and every auth read threw NotFoundError
// permanently — an unrecoverable logout until site data was cleared.
const IDB_NAME = 'smartreminder-db'
const IDB_STORE = 'auth'
const IDB_VERSION = 2

function openAuthDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(IDB_NAME, IDB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(IDB_STORE)) db.createObjectStore(IDB_STORE)
    }
    req.onsuccess = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(IDB_STORE)) {
        db.close()
        reject(new Error('idb: auth object store missing'))
        return
      }
      resolve(db)
    }
    req.onerror = () => reject(req.error)
    req.onblocked = () => reject(new Error('idb: upgrade blocked'))
  })
}

interface AuthFetchOptions extends RequestInit {
  actionToken?: string
}

async function fetchWithAuth(url: string, options: AuthFetchOptions) {
  let token: string | null = null
  try {
    const db = await openAuthDb()
    token = await new Promise<string | null>((resolve, reject) => {
      const tx = db.transaction(IDB_STORE, 'readonly')
      const req = tx.objectStore(IDB_STORE).get('access_token')
      req.onsuccess = () => resolve((req.result as string) ?? null)
      req.onerror = () => reject(req.error)
      tx.onabort = () => reject(tx.error)
    })
  } catch {
    // Fall through to the action_token below.
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string>) ?? {}),
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`
  } else if (options.actionToken) {
    headers.Authorization = `Bearer ${options.actionToken}`
  }

  return fetch(url, { ...options, headers })
}

// ── Lifecycle ───────────────────────────────────────────────────────────────

self.addEventListener('install', () => {
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim())
})

// ── Push ────────────────────────────────────────────────────────────────────

self.addEventListener('push', (event) => {
  if (!event.data) return

  try {
    const data = event.data.json()

    if (data.type === 'cancel') {
      event.waitUntil(
        self.registration.getNotifications({ tag: data.tag }).then((notifications) => {
          notifications.forEach((n) => n.close())
        }),
      )
      return
    }

    if (data.type === 'test') {
      event.waitUntil(
        self.registration.showNotification(data.title || 'SmartRemind', {
          body: data.body || 'Notifications are working.',
          tag: data.tag || 'test-push',
          icon: ICON,
          badge: BADGE,
        }),
      )
    }

    if (data.type === 'reminder') {
      event.waitUntil(
        self.registration.showNotification(data.title, {
          body: `Due: ${new Date(data.due_at).toLocaleTimeString()}`,
          tag: data.tag,
          icon: ICON,
          badge: BADGE,
          actions: [
            { action: 'done', title: 'Done' },
            { action: 'snooze', title: 'Snooze 10m' },
          ],
          data: { task_id: data.task_id, due_at: data.due_at, action_token: data.action_token },
        } as NotificationOptions),
      )
    }

    if (data.type === 'summary_ready') {
      event.waitUntil(
        self.registration.showNotification(data.title, {
          body: data.body,
          tag: data.tag,
          icon: ICON,
          badge: BADGE,
          data: { summary: data.summary, url: '/summary' },
        }),
      )
    }

    if (data.type === 'checkin') {
      event.waitUntil(
        self.registration.showNotification("How's it going?", {
          body: 'Log how the last hour went.',
          tag: data.tag,
          icon: ICON,
          badge: BADGE,
          // NOTE: Android Chrome silently caps visible action buttons at 2.
          // Keep the two most important actions first so they always appear.
          actions: [
            { action: 'productive', title: '✅ Productive' },
            { action: 'not_productive', title: '❌ Not productive' },
            { action: 'remind_later', title: '⏰ Remind later' },
          ],
          // Keep the notification on screen until the user explicitly acts.
          // Without this it auto-dismisses on Android before the user taps.
          requireInteraction: true,
          data: { action_token: data.action_token, reminder_id: data.reminder_id },
        } as NotificationOptions),
      )
    }
  } catch (err) {
    console.error('[SW] push handling failed', err)
  }
})

// ── Notification clicks ─────────────────────────────────────────────────────

async function focusOrOpen(targetUrl: string, message?: unknown) {
  const clientList = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
  for (const client of clientList) {
    if (client.url.includes(self.location.origin)) {
      if (message) client.postMessage(message)
      await client.focus()
      return client.navigate(targetUrl)
    }
  }
  return self.clients.openWindow(targetUrl)
}

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const { task_id, action_token, summary, url, reminder_id } = event.notification.data || {}
  const action = event.action  // capture once; used in the fall-through guard below

  if (url === '/summary') {
    event.waitUntil(focusOrOpen('/summary', { type: 'SUMMARY_READY', summary }))
    return
  }

  if (event.action === 'done' || event.action === 'snooze') {
    event.waitUntil(
      fetchWithAuth(`${API_BASE}/tasks/${task_id}/action`, {
        method: 'POST',
        actionToken: action_token,
        body: JSON.stringify({
          action: event.action,
          client_timestamp: new Date().toISOString(),
          ...(event.action === 'snooze' ? { snooze_minutes: 10 } : {}),
        }),
      }),
    )
    return
  }

  if (['productive', 'average', 'not_productive'].includes(event.action)) {
    const statusMap: Record<string, string> = {
      productive: 'focused',
      average: 'idle',
      not_productive: 'distracted',
    }
    event.waitUntil(
      fetchWithAuth(`${API_BASE}/companion/checkin`, {
        method: 'POST',
        actionToken: action_token,
        body: JSON.stringify({
          status: statusMap[event.action],
          start_at: new Date(Date.now() - 3_600_000).toISOString(),
          end_at: new Date().toISOString(),
          reminder_id,
        }),
      }).then(async () => {
        const clientList = await self.clients.matchAll({ type: 'window' })
        clientList.forEach((c) => c.postMessage({ type: 'CHECKIN_LOGGED' }))
      }),
    )
    return
  }

  if (event.action === 'add_task') {
    event.waitUntil(focusOrOpen('/?new=1', { type: 'OPEN_ADD_TASK_MODAL' }))
    return
  }

  if (event.action === 'remind_later') {
    event.waitUntil(
      fetchWithAuth(`${API_BASE}/companion/checkin/reschedule`, {
        method: 'POST',
        actionToken: action_token,
      }),
    )
    return
  }

  // Safety guard: if we reach here with a named action it means none of the
  // branches above matched (unknown future action). Do nothing — do NOT open
  // the app for an unrecognised action.
  // On some Android Chrome builds, tapping a named action button fires two
  // notificationclick events: one with event.action === 'productive' (handled
  // and returned above) and a second spurious one with event.action === ''.
  // Without this guard that second event falls through to focusOrOpen and
  // opens the app even though the user only tapped an action button.
  if (action !== '') return

  // Body tap (action === ''). Check-ins deep-link into the check-in sheet;
  // everything else just opens the app. Note these target '/' now that
  // Dashboard and Tasks are merged — App.tsx keeps a permanent /dashboard
  // redirect for workers installed before this release.
  const isCheckin = event.notification.tag === 'hourly-checkin'
  const targetUrl = isCheckin
    ? `/?checkin=1${reminder_id ? `&reminderId=${reminder_id}` : ''}`
    : '/'

  event.waitUntil(
    focusOrOpen(targetUrl, isCheckin ? { type: 'OPEN_CHECKIN_PANEL', reminderId: reminder_id } : undefined),
  )
})
