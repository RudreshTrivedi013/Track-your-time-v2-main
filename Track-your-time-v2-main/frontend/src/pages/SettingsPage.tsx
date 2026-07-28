import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { useAuthStore } from '@/stores/authStore'
import { useAuth } from '@/hooks/useAuth'
import { authApi } from '@/api/auth'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { LogOut } from '@/lib/icons'
import { cn, parseApiError } from '@/lib/utils'

/**
 * Down from ~430 lines to the two things a user actually sets.
 *
 * Removed: the account profile card (email and timezone, both read-only), the
 * daily-summary and task-reminder toggles, the check-in interval picker, the
 * web-push registration card, the connected-devices list, per-device Ping and
 * Test Notifications. Those last four were developer tooling that shipped to
 * production; device UUIDs are not something a user can act on.
 *
 * Push permission is no longer a setting at all — it is requested in context
 * when a reminder with a due date is saved. See lib/push-prompt.tsx.
 */

const WORK_HOUR_PRESETS = [
  { id: 'short', label: 'Short', hours: '9 AM – 5 PM', start: '09:00:00', end: '17:00:00' },
  { id: 'standard', label: 'Standard', hours: '9 AM – 7 PM', start: '09:00:00', end: '19:00:00' },
  { id: 'long', label: 'Long', hours: '8 AM – 9 PM', start: '08:00:00', end: '21:00:00' },
] as const

export default function SettingsPage() {
  const { user, setUser } = useAuthStore()
  const { logout } = useAuth()
  const navigate = useNavigate()

  const [start, setStart] = useState(user?.working_hours_start ?? '09:00:00')
  const [end, setEnd] = useState(user?.working_hours_end ?? '17:00:00')
  const [checkinEnabled, setCheckinEnabled] = useState(user?.checkin_enabled ?? true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!user) return
    setStart(user.working_hours_start)
    setEnd(user.working_hours_end)
    setCheckinEnabled(user.checkin_enabled)
  }, [user])

  const handleSave = async () => {
    setSaving(true)
    try {
      // Send ONLY the fields this screen owns. The old version PATCHed its
      // whole local settings object, so saving work hours could clobber
      // reminders_enabled or daily_summary_enabled with stale state.
      const updated = await authApi.updateMe({
        working_hours_start: start,
        working_hours_end: end,
        checkin_enabled: checkinEnabled,
      })
      setUser(updated)
      toast.success('Saved')
    } catch (err) {
      toast.error(parseApiError(err))
    } finally {
      setSaving(false)
    }
  }

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <div className="w-full max-w-lg space-y-6">
      <h1 className="text-xl font-semibold tracking-tight text-text-primary">Settings</h1>

      <section className="space-y-3">
        <div>
          <h2 className="text-base font-semibold text-text-primary">Working hours</h2>
          <p className="text-xs text-text-secondary">
            Reminders outside these hours wait until you're back.
          </p>
        </div>

        <div className="space-y-2">
          {WORK_HOUR_PRESETS.map((preset) => {
            const active = start === preset.start && end === preset.end
            return (
              <button
                key={preset.id}
                type="button"
                onClick={() => {
                  setStart(preset.start)
                  setEnd(preset.end)
                }}
                aria-pressed={active}
                className={cn(
                  'flex min-h-[56px] w-full items-center justify-between rounded-xl border px-4 text-left transition-colors',
                  active
                    ? 'border-white bg-white text-bg'
                    : 'border-border bg-bg-surface text-text-primary hover:bg-white/5',
                )}
              >
                <span className="text-sm font-medium">{preset.label}</span>
                <span className={cn('text-xs', active ? 'text-bg/70' : 'text-text-secondary')}>
                  {preset.hours}
                </span>
              </button>
            )
          })}
        </div>
      </section>

      <section className="flex items-center justify-between gap-4 border-t border-border pt-5">
        <div className="min-w-0">
          <h2 className="text-sm font-medium text-text-primary">Hourly check-ins</h2>
          <p className="text-xs text-text-secondary">
            A quick "how's it going?" during working hours.
          </p>
        </div>
        <Switch
          checked={checkinEnabled}
          onCheckedChange={setCheckinEnabled}
          aria-label="Hourly check-ins"
        />
      </section>

      <Button className="w-full" onClick={handleSave} disabled={saving}>
        {saving ? 'Saving…' : 'Save'}
      </Button>

      <div className="border-t border-border pt-5">
        <Button variant="ghost" className="w-full md:hidden" onClick={handleLogout}>
          <LogOut className="size-4" />
          Sign out
        </Button>
      </div>
    </div>
  )
}
