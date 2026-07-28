import toast from 'react-hot-toast'
import { PushDeniedError, registerPushSubscription } from '@/lib/sw-registration'

/**
 * Contextual notification-permission prompt.
 *
 * Shown right after a reminder with a due date is saved — the one moment where
 * "we need permission to actually reach you" is self-evident rather than an
 * abstract request on arrival. Re-asked on every such save while permission is
 * still missing, because a reminder that can't fire is the product not working.
 *
 * Not shown for `denied`: the browser will not re-prompt and only site/OS
 * settings can undo it, so a toast on every save would be pure noise. The
 * NotificationPermission notice explains that state instead.
 *
 * The Enable button calls registerPushSubscription() directly from the click
 * so the user activation Chrome requires is still live when
 * requestPermission() runs.
 */
export function maybePromptForPush(): void {
  if (typeof Notification === 'undefined') return
  if (Notification.permission !== 'default') return

  toast(
    (t) => (
      <div className="flex flex-col gap-2">
        <span className="text-sm">Allow notifications so this reminder can reach you.</span>
        <div className="flex gap-2">
          <button
            type="button"
            className="min-h-[36px] flex-1 rounded-lg bg-white px-3 text-xs font-medium text-bg"
            onClick={async () => {
              toast.dismiss(t.id)
              try {
                await registerPushSubscription()
                toast.success('Notifications enabled')
              } catch (err) {
                if (err instanceof PushDeniedError) {
                  toast.error('Permission dismissed — you can enable it from the banner on Home.')
                } else {
                  toast.error("Couldn't enable notifications")
                  console.error('[push-prompt]', err)
                }
              }
            }}
          >
            Enable
          </button>
          <button
            type="button"
            className="min-h-[36px] flex-1 rounded-lg border border-border px-3 text-xs text-text-secondary"
            onClick={() => toast.dismiss(t.id)}
          >
            Not now
          </button>
        </div>
      </div>
    ),
    { duration: 8000 },
  )
}
