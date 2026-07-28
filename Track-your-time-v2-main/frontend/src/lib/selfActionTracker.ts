/**
 * Tracks task mutations this tab just made, so the WebSocket handler can
 * skip re-invalidating the task list when the server echoes that same
 * action back to us — the mutation's own onSettled already covers it.
 *
 * Without this, every Done/Snooze/Reopen/Edit/Delete triggers two full
 * `GET /tasks` refetches back to back (one from the mutation, one from the
 * WS echo), doubling round trips to the database for no benefit on the
 * tab that made the change. Other tabs/devices still get the real-time
 * invalidation as normal — this only suppresses the self-echo.
 */

const recentSelfActions = new Map<string, number>()
const TTL_MS = 4000

export function markSelfAction(taskId: string) {
  recentSelfActions.set(taskId, Date.now())
}

export function isRecentSelfAction(taskId: string): boolean {
  const at = recentSelfActions.get(taskId)
  if (at === undefined) return false
  if (Date.now() - at > TTL_MS) {
    recentSelfActions.delete(taskId)
    return false
  }
  return true
}
