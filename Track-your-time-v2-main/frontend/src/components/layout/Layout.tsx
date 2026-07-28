import { useEffect, useState } from 'react'
import { Outlet, useLocation, useSearchParams } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { BottomNav } from './BottomNav'
import { Fab } from './Fab'
import { useWebSocket } from '@/hooks/useWebSocket'
import { NotificationPermission } from '@/components/notifications/NotificationPermission'
import { useDeviceStore } from '@/stores/deviceStore'
import { devicesApi } from '@/api/devices'
import { initServiceWorker } from '@/lib/sw-registration'
import { CheckinSheet } from '@/components/checkin/CheckinSheet'
import { TaskFormSheet } from '@/components/tasks/TaskFormSheet'
import { useCheckinPanelStore } from '@/stores/checkinPanelStore'

const PING_INTERVAL_MS = 5 * 60 * 1000 // 5 minutes

/**
 * The app shell. Mounted ONCE, as a react-router layout route (see App.tsx) —
 * pages render through <Outlet/> rather than being passed in as children.
 *
 * This distinction is load-bearing, not stylistic. When each route wrapped its
 * own <Layout>{page}</Layout>, react-router unmounted and remounted the whole
 * shell on every navigation, which re-ran every effect below: a fresh
 * WebSocket handshake, initServiceWorker() (POST /devices + an sw.js fetch),
 * and an immediate device ping — roughly four redundant network calls per
 * in-app navigation, doubled again by StrictMode in dev.
 */
export function Layout() {
  useWebSocket()
  const { deviceId } = useDeviceStore()
  const { pathname } = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const { isOpen: isCheckinOpen, reminderId, open: openCheckin, close: closeCheckin } = useCheckinPanelStore()
  const [isCreateTaskOpen, setIsCreateTaskOpen] = useState(false)

  // Notification-driven deep links. `addTask` is the legacy param name still
  // emitted by service workers installed before this release; `new` is what
  // the current one (and the manifest shortcut) uses. Accept both.
  useEffect(() => {
    const shouldOpenCheckin = searchParams.get('checkin') === '1'
    const newReminderId = searchParams.get('reminderId') ?? undefined
    const shouldOpenAddTask = searchParams.get('addTask') === '1' || searchParams.get('new') === '1'

    if (shouldOpenCheckin || newReminderId) {
      openCheckin(newReminderId)
    }
    if (shouldOpenAddTask) {
      setIsCreateTaskOpen(true)
    }
    if (shouldOpenCheckin || newReminderId || shouldOpenAddTask) {
      setSearchParams(
        (prev) => {
          prev.delete('checkin')
          prev.delete('reminderId')
          prev.delete('addTask')
          prev.delete('new')
          return prev
        },
        { replace: true },
      )
    }
  }, [searchParams, setSearchParams, openCheckin])

  // Service worker messages for the same two panels.
  useEffect(() => {
    const handleSwMessage = (event: MessageEvent) => {
      if (event.data?.type === 'OPEN_CHECKIN_PANEL') {
        openCheckin(event.data.reminderId ?? undefined)
      }
      if (event.data?.type === 'OPEN_ADD_TASK_MODAL') {
        setIsCreateTaskOpen(true)
      }
    }
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.addEventListener('message', handleSwMessage)
    }
    return () => {
      if ('serviceWorker' in navigator) {
        navigator.serviceWorker.removeEventListener('message', handleSwMessage)
      }
    }
  }, [openCheckin])

  // Auto-register the Service Worker and push subscription on every
  // authenticated page load. If permission was already granted in a previous
  // session this runs silently and ensures the device is always registered.
  useEffect(() => {
    initServiceWorker().catch(() => {
      // Silently ignore — NotificationPermission and the contextual prompt
      // in TaskFormSheet handle the user-facing side.
    })
  }, [])

  // Keep `last_active_at` fresh so the backend can target the active device
  // for notifications (and prune stale subscriptions via GoneException).
  useEffect(() => {
    if (!deviceId) return
    const ping = () => {
      devicesApi.ping(deviceId).catch(() => {
        // Non-critical heartbeat.
      })
    }
    ping()
    const interval = setInterval(ping, PING_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [deviceId])

  return (
    <div className="flex min-h-dvh bg-bg">
      <Sidebar />
      <main className="relative flex-1">
        <NotificationPermission />
        {/* Clear the 56px bottom nav AND the home indicator beneath it. */}
        <div className="mx-auto max-w-[1100px] px-4 py-5 pb-[calc(5.5rem+env(safe-area-inset-bottom,0px))] md:pb-6">
          <Outlet />
        </div>
      </main>
      <BottomNav />

      {pathname === '/' && <Fab onClick={() => setIsCreateTaskOpen(true)} />}

      <CheckinSheet open={isCheckinOpen} reminderId={reminderId} onClose={closeCheckin} />
      <TaskFormSheet open={isCreateTaskOpen} onClose={() => setIsCreateTaskOpen(false)} />
    </div>
  )
}
