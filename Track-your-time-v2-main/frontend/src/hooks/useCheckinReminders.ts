/**
 * The query key only. The useCheckinReminders() hook that used to live here
 * was never called by anything — CheckinSheet and main.tsx just invalidate
 * this key after a check-in is logged.
 */
export const CHECKIN_REMINDERS_KEY = ['checkinReminders'] as const
