import { devicesApi } from '@/api/devices'
import { useDeviceStore } from '@/stores/deviceStore'

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const rawData = atob(base64)
  return Uint8Array.from([...rawData].map((char) => char.charCodeAt(0)))
}

export class PushUnsupportedError extends Error {}
export class PushDeniedError extends Error {}

/**
 * Full push subscription flow. Must be called directly from a click handler.
 *
 * ORDER IS CRITICAL: Notification.requestPermission() runs FIRST, before any
 * other await.
 *
 * Chrome only opens the permission prompt while the page holds "transient user
 * activation", which expires a few seconds after the click and is consumed by
 * intervening async work. The previous version awaited
 * serviceWorker.register(), registration.update() (a network fetch of sw.js)
 * and serviceWorker.ready before asking — by which point activation was gone,
 * so requestPermission() resolved to 'default' immediately and the prompt
 * never appeared. Nothing threw, so it looked like the button did nothing.
 */
export async function registerPushSubscription(): Promise<void> {
  if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
    throw new PushUnsupportedError('Push notifications are not supported in this browser')
  }

  const vapidKey = import.meta.env.VITE_VAPID_PUBLIC_KEY as string
  if (!vapidKey || vapidKey === 'your_vapid_public_key_here') {
    throw new Error('VITE_VAPID_PUBLIC_KEY is not configured')
  }

  // 1. Ask while we still have user activation.
  const permission =
    Notification.permission === 'granted' ? 'granted' : await Notification.requestPermission()

  if (permission !== 'granted') {
    throw new PushDeniedError(
      permission === 'denied'
        ? 'Notifications are blocked for this site'
        : 'Notification permission was dismissed',
    )
  }

  // 2. Only now do the slow service-worker work.
  const registration = await navigator.serviceWorker.register(
    import.meta.env.DEV ? '/dev-sw.js?dev-sw' : '/sw.js',
    { type: import.meta.env.DEV ? 'module' : 'classic' }
  )
  await navigator.serviceWorker.ready

  await _subscribeAndRegister(registration, vapidKey)
}

/**
 * Silent auto-init called on every authenticated page load.
 *
 * - If the SW is not yet registered, registers it.
 * - If permission is already 'granted', creates (or refreshes) the push
 *   subscription and registers the device with the backend.
 * - Does NOT prompt for permission — use registerPushSubscription() for that.
 */
export async function initServiceWorker(): Promise<void> {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
    return
  }

  const vapidKey = import.meta.env.VITE_VAPID_PUBLIC_KEY as string
  if (!vapidKey || vapidKey === 'your_vapid_public_key_here') {
    return
  }

  try {
    const registration = await navigator.serviceWorker.register(
      import.meta.env.DEV ? '/dev-sw.js?dev-sw' : '/sw.js',
      { type: import.meta.env.DEV ? 'module' : 'classic' }
    )
    // Safe to force an update check here — unlike registerPushSubscription()
    // this path never prompts, so there is no user activation to burn.
    await registration.update().catch(() => undefined)
    await navigator.serviceWorker.ready

    // Never prompts. If permission is 'default' the NotificationPermission
    // notice offers it, and TaskFormSheet asks again on each due-dated save.
    if (Notification.permission !== 'granted') {
      return
    }

    await _subscribeAndRegister(registration, vapidKey)
  } catch (err) {
    // Non-fatal — do not crash the app on SW errors.
    console.warn('[SW] initServiceWorker failed silently:', err)
  }
}

/**
 * Internal helper: subscribe to push and POST the subscription to /devices.
 */
async function _subscribeAndRegister(
  registration: ServiceWorkerRegistration,
  vapidKey: string,
): Promise<void> {
  let subscription = await registration.pushManager.getSubscription()

  if (!subscription) {
    subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(vapidKey) as any,
    })
    console.info('[SW] New push subscription created')
  } else {
    console.info('[SW] Existing push subscription found')
  }

  // Register with backend and store the device ID for auto-ping.
  const device = await devicesApi.register(JSON.stringify(subscription), true)
  useDeviceStore.getState().setDeviceId(device.id)
  console.info('[SW] Device registered with backend — id:', device.id)
}

export async function unregisterServiceWorker(): Promise<void> {
  if (!('serviceWorker' in navigator)) return
  const registrations = await navigator.serviceWorker.getRegistrations()
  await Promise.all(registrations.map((r) => r.unregister()))
  useDeviceStore.getState().clearDevice()
}
