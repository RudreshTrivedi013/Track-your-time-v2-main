/**
 * Auth store with IndexedDB persistence for the access token.
 *
 * WHY IndexedDB (not localStorage):
 * Service workers cannot access localStorage — it's only available on the
 * main thread. IndexedDB is available in both the main thread AND service
 * workers, so storing the access token there lets the SW authenticate
 * in-notification "Done" / "Snooze" action buttons without an action_token.
 */
import { create } from 'zustand'
import type { User } from '@/types/api'

const IDB_NAME = 'smartreminder-db'
const IDB_STORE = 'auth'
// v2, not v1. An older public/sw.js opened this database at version 1 without
// an onupgradeneeded handler, which could create it with ZERO object stores.
// Once that happened, opening at v1 from here never fired an upgrade, so every
// transaction('auth') threw NotFoundError forever — auth was permanently dead
// until the user cleared site data. Bumping the version forces an upgrade that
// repairs those databases in place.
// KEEP IN SYNC with the identical constants and openDb() in public/sw.js.
const IDB_VERSION = 2

// ── IndexedDB helpers ──────────────────────────────────────────────────────

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(IDB_NAME, IDB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(IDB_STORE)) {
        db.createObjectStore(IDB_STORE)
      }
    }
    req.onsuccess = () => {
      const db = req.result
      // Belt and braces: if the store is still missing we are in the poisoned
      // state described above. Reject so the caller can self-heal.
      if (!db.objectStoreNames.contains(IDB_STORE)) {
        db.close()
        reject(new Error('idb: auth object store missing'))
        return
      }
      resolve(db)
    }
    req.onerror = () => reject(req.error)
    // Another tab holds an open connection at the old version.
    req.onblocked = () => reject(new Error('idb: upgrade blocked by another tab'))
  })
}

/** Nuke and recreate the database. Losing a cached access token is harmless —
 *  the refresh token in localStorage recovers the session. Staying bricked is not. */
function deleteDb(): Promise<void> {
  return new Promise((resolve) => {
    const req = indexedDB.deleteDatabase(IDB_NAME)
    req.onsuccess = () => resolve()
    req.onerror = () => resolve()
    req.onblocked = () => resolve()
  })
}

export async function idbSetToken(token: string): Promise<void> {
  try {
    const db = await openDb()
    // NOTE: `return await` is load-bearing. `return new Promise(...)` inside a
    // try block does NOT route the promise's rejection through the catch, so a
    // NotFoundError here used to escape as an unhandled rejection.
    return await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(IDB_STORE, 'readwrite')
      tx.objectStore(IDB_STORE).put(token, 'access_token')
      tx.oncomplete = () => resolve()
      tx.onerror = () => reject(tx.error)
      tx.onabort = () => reject(tx.error)
    })
  } catch {
    // Silently fail — IDB is not critical for main-thread auth
  }
}

export async function idbGetToken(): Promise<string | null> {
  const read = async (): Promise<string | null> => {
    const db = await openDb()
    return await new Promise<string | null>((resolve, reject) => {
      const tx = db.transaction(IDB_STORE, 'readonly')
      const req = tx.objectStore(IDB_STORE).get('access_token')
      req.onsuccess = () => resolve((req.result as string) ?? null)
      req.onerror = () => reject(req.error)
      tx.onabort = () => reject(tx.error)
    })
  }

  try {
    return await read()
  } catch {
    // One-shot self-heal for a corrupted/store-less database, then give up.
    try {
      await deleteDb()
      return await read()
    } catch {
      return null
    }
  }
}

export async function idbClearToken(): Promise<void> {
  try {
    const db = await openDb()
    return await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(IDB_STORE, 'readwrite')
      tx.objectStore(IDB_STORE).delete('access_token')
      tx.oncomplete = () => resolve()
      tx.onerror = () => reject(tx.error)
      tx.onabort = () => reject(tx.error)
    })
  } catch {
    // Silently fail
  }
}

// ── Zustand store ──────────────────────────────────────────────────────────

interface AuthState {
  accessToken: string | null
  user: User | null
  isAuthenticated: boolean

  setAuth: (accessToken: string, user: User) => void
  setAccessToken: (accessToken: string) => void

  // NEW: Update only the user object without affecting auth state.
  setUser: (user: User) => void

  clearAuth: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  user: null,
  isAuthenticated: false,

  setAuth: (accessToken, user) => {
    idbSetToken(accessToken)
    set({ accessToken, user, isAuthenticated: true })
  },

  setAccessToken: (accessToken) => {
    idbSetToken(accessToken)
    set({ accessToken, isAuthenticated: true })
  },

  // NEW
  setUser: (user) => {
    set({ user })
  },

  clearAuth: () => {
    localStorage.removeItem('refresh_token')
    idbClearToken()
    set({ accessToken: null, user: null, isAuthenticated: false })
  },
}))

// ── Session teardown ───────────────────────────────────────────────────────

/** True only for genuine credential rejections. A network failure, a CORS
 *  block, a cold-starting backend or a 500 must NOT be treated as "logged out"
 *  — doing so used to wipe a perfectly good refresh token on one flaky request.
 *
 *  ONLY 401 counts. 403 can come from CORS blocks, WAF rules, permission
 *  checks, or WebSocket policy violations — none of which mean "your refresh
 *  token is invalid". Treating 403 as a logout trigger was destroying valid
 *  sessions on transient infrastructure hiccups. */
export function isAuthError(err: unknown): boolean {
  const status = (err as { response?: { status?: number } })?.response?.status
  return status === 401
}

/**
 * Tear down the session completely.
 *
 * Unlike clearAuth(), this AWAITS the IndexedDB delete before navigating —
 * otherwise the transaction is aborted by the navigation and the stale token
 * survives to be picked up on the next boot, producing a redirect loop.
 *
 * Pass { navigate: false } during boot (the router has not mounted yet, and
 * ProtectedRoute will redirect on its own) and whenever the user is already
 * looking at an auth page — a reload there destroys the error toast they are
 * supposed to be reading.
 */
export async function hardLogout({ navigate = true }: { navigate?: boolean } = {}): Promise<void> {
  localStorage.removeItem('refresh_token')
  localStorage.removeItem('refresh_token_at')
  await idbClearToken()
  useAuthStore.getState().clearAuth()

  if (!navigate) return
  const path = window.location.pathname
  if (path !== '/login' && path !== '/signup') {
    window.location.replace('/login')
  }
}