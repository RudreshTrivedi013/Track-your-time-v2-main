import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { PushDeniedError, registerPushSubscription } from '@/lib/sw-registration'
import { useDeviceStore } from '@/stores/deviceStore'

/**
 * A slim, always-available way to turn notifications on.
 *
 * This is an ASK, not a disable switch — there is deliberately no way to turn
 * notifications off here, because a reminder app whose reminders are off is
 * just a list. The contextual prompt in TaskFormSheet covers the moment of
 * need; this covers the user who goes looking for it instead.
 *
 * Three states:
 *  - default   → "Turn on notifications" + Enable
 *  - no_device → permission granted but registration failed (network blip,
 *                rotated VAPID key). Silently broken otherwise: the user
 *                believes reminders work and never finds out they don't.
 *  - denied    → only browser/OS settings can undo this, so say so plainly
 *                and offer no button that cannot work.
 */
type Reason = 'default' | 'no_device' | 'denied'

const COPY: Record<Reason, { text: string; cta?: string }> = {
  default: { text: 'Turn on notifications so your reminders can reach you.', cta: 'Enable' },
  no_device: { text: "This device isn't registered for notifications.", cta: 'Fix' },
  denied: {
    text: 'Notifications are blocked in your browser settings — reminders can’t reach you.',
  },
}

export function NotificationPermission() {
  const [reason, setReason] = useState<Reason | null>(null)
  const [busy, setBusy] = useState(false)
  const { deviceId } = useDeviceStore()

  const sync = () => {
    if (!('Notification' in window)) return setReason(null)
    if (Notification.permission === 'denied') return setReason('denied')
    if (Notification.permission === 'default') return setReason('default')
    setReason(deviceId ? null : 'no_device')
  }

  useEffect(sync, [deviceId])

  const handleEnable = async () => {
    setBusy(true)
    try {
      // Called directly from the click so Chrome still has user activation —
      // requestPermission() silently no-ops without it.
      await registerPushSubscription()
      toast.success('Notifications enabled')
    } catch (err) {
      if (err instanceof PushDeniedError) {
        toast.error(
          Notification.permission === 'denied'
            ? 'Blocked. Allow notifications for this site in your browser settings.'
            : 'Permission dismissed — tap Enable to try again.',
        )
      } else {
        toast.error("Couldn't enable notifications")
        console.error('[NotificationPermission]', err)
      }
    } finally {
      setBusy(false)
      sync()
    }
  }

  if (!reason) return null
  const { text, cta } = COPY[reason]

  return (
    <div className="flex items-center justify-between gap-3 border-b border-border bg-white/[0.03] px-4 py-2.5">
      <p className="text-xs text-text-secondary">{text}</p>
      {cta && (
        <button
          type="button"
          onClick={handleEnable}
          disabled={busy}
          className="min-h-[36px] shrink-0 rounded-lg bg-white px-3 text-xs font-medium text-bg disabled:opacity-50"
        >
          {busy ? 'Working…' : cta}
        </button>
      )}
    </div>
  )
}
