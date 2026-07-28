import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { format, formatDistanceToNow, isToday, isTomorrow, parseISO } from 'date-fns'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDueDate(dateStr: string | null): string {
  if (!dateStr) return ''
  try {
    const date = parseISO(dateStr)
    const timeStr = format(date, 'h:mm a')
    if (isToday(date)) return `Today ${timeStr}`
    if (isTomorrow(date)) return `Tomorrow ${timeStr}`
    return format(date, 'MMM d, yyyy · h:mm a')
  } catch {
    return dateStr
  }
}

export function formatRelative(dateStr: string): string {
  try {
    return formatDistanceToNow(parseISO(dateStr), { addSuffix: true })
  } catch {
    return dateStr
  }
}

export function formatTime(dateStr: string): string {
  try {
    return format(parseISO(dateStr), 'h:mm a')
  } catch {
    return dateStr
  }
}

export function formatDate(dateStr: string): string {
  try {
    return format(parseISO(dateStr), 'MMM d, yyyy')
  } catch {
    return dateStr
  }
}

export function parseApiError(error: unknown): string {
  if (!error) return 'An unexpected error occurred'
  const err = error as { response?: { data?: { detail?: unknown } }; message?: string }
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((d: { msg?: string }) => d?.msg ?? '').join(', ')
  }
  return err?.message ?? 'An unexpected error occurred'
}

// Used only where Intl.supportedValuesOf is unavailable (older Safari).
const FALLBACK_TIMEZONES = [
  'UTC', 'America/New_York', 'America/Chicago', 'America/Denver',
  'America/Los_Angeles', 'America/Anchorage', 'Pacific/Honolulu',
  'Europe/London', 'Europe/Paris', 'Europe/Berlin', 'Europe/Moscow',
  'Asia/Dubai', 'Asia/Kolkata', 'Asia/Shanghai', 'Asia/Tokyo',
  'Asia/Singapore', 'Australia/Sydney', 'Pacific/Auckland',
]

/**
 * The full IANA zone list, not a hand-picked 18.
 *
 * The old list could not represent most of the world, so a user in, say,
 * Asia/Kathmandu got a detected default with no matching <option>: the select
 * showed UTC, the form value read back empty, and signup hard-failed with
 * "Please select your timezone". Picking a wrong-but-listed zone then silently
 * corrupted quiet hours and daily-summary scheduling.
 */
export const TIMEZONES: string[] = (() => {
  const supportedValuesOf = (Intl as unknown as {
    supportedValuesOf?: (key: string) => string[]
  }).supportedValuesOf

  try {
    const zones = supportedValuesOf?.('timeZone')
    if (zones?.length) return zones
  } catch {
    // fall through
  }
  return FALLBACK_TIMEZONES
})()

/** The browser's zone, guaranteed to be selectable in TIMEZONES. */
export function detectTimezone(): string {
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone
    if (tz && TIMEZONES.includes(tz)) return tz
  } catch {
    // fall through
  }
  return 'UTC'
}
