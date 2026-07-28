# Smart Reminder / Task Management Backend

FastAPI + Postgres + Celery backend for a voice-aware, multi-device reminder
app. Backend only (per spec) — no frontend included.

## Stack
FastAPI (async) · PostgreSQL via async SQLAlchemy 2.0 + asyncpg · Alembic ·
JWT auth (python-jose + passlib) · Celery + Celery beat on Redis ·
Groq API (voice parsing + day-end summaries) · pywebpush ·
docker-compose for local dev.

## Quick start

1. Copy `.env.example` to `.env` and fill in real values — at minimum
   `JWT_SECRET_KEY`, `GROQ_API_KEY`, and `VAPID_PUBLIC_KEY` /
   `VAPID_PRIVATE_KEY` (generate with `python -m pywebpush.vapid` or
   `npx web-push generate-vapid-keys`).
2. `docker compose up --build`
3. Visit `http://localhost:8000/docs` for interactive Swagger UI; `/health`
   should return `{"status": "ok"}`.
4. Run migrations (first time / after model changes):
   `docker compose exec backend alembic upgrade head`
5. Run tests: `docker compose exec backend pytest -v`

Full command list is at the bottom of this file.

## Project layout

```
app/
  main.py            FastAPI app + route registration, /health
  config.py          pydantic-settings, reads .env
  database.py         async engine + session factory
  models/             SQLAlchemy: user, task, task_note, device, notification_log
  schemas/             Pydantic request/response + the voice-parsing schema
                        Claude's output is validated against
  api/                route handlers (auth, tasks, voice, devices, summary, ws)
  services/            business logic, separate from routes:
                          auth_service, task_service (state machine),
                          claude_service (LLM calls + validation),
                          push_service, device_service
  workers/             celery_app.py, reminder_tasks.py, summary_tasks.py
  websocket/           connection_manager.py + the /ws route
  core/                security.py (JWT/password hashing), deps.py (auth dep)
alembic/               migrations (one hand-written initial migration included)
tests/                 pytest: state-machine unit tests + voice fixture tests
fixtures/              voice_transcripts.json — transcript -> expected JSON
```

## Design decisions (so you can defend them)

**Why scheduling is server-driven (Celery beat), not client timers.**
A `setTimeout`/JS-interval-based reminder dies the instant a tab closes, a
phone goes to sleep, or the OS kills the background app — exactly the
moments a reminder app most needs to still work. Celery beat runs as an
independent process on the server, completely decoupled from whether any
client is even open, so "what's due right now" has one single source of
truth and one clock. It also sidesteps per-device clock skew: the server
decides what's due, not whichever phone happens to be awake.

**Why Claude's output is validated against a Pydantic schema, not trusted
directly.** The LLM is an untrusted external input in an otherwise fully
typed system — it can hallucinate fields, return slightly malformed JSON,
guess a wrong date format, or wrap output in markdown fences. `claude_service.py`
strips fences, `json.loads`s the result, and then runs it through
`ParsedVoiceResult.model_validate(...)` (or `SummaryOut` for the day-end
summary) before anything downstream ever sees it. If validation fails we
raise and surface a 502 to the client rather than silently writing bad data
or guessing. Voice-parsed results are also never auto-saved — `/tasks/parse-voice`
only returns a draft for the user to confirm, so even a subtly wrong parse
can't silently create a task.

**Why every timestamp is stored in UTC.** `due_at` / `next_due_at` /
`snoozed_until` / `anchor_time` are all UTC so "is this due" is a single
`<= now_utc` comparison in the scheduling hot path, with no DST or
timezone-conversion ambiguity. Local time only enters at the edges where it's
actually the meaningful unit: quiet-hours math (`reminder_tasks.py`) and
deciding when "9pm" is for each user's day-end summary
(`summary_tasks.py`) — both convert UTC to the user's IANA timezone via
`zoneinfo`, do the comparison, and convert back to UTC before touching the
database.

**Idempotency / last-write-wins.** Every task carries `last_action_client_ts`.
`task_service.apply_action()` rejects (no-ops) any action whose
`client_timestamp` isn't strictly newer than what's already been applied —
so replays are no-ops, and out-of-order delivery from a flaky mobile
connection can't undo a newer action with a stale one. This is ordering by
*client-asserted event time*, not by server arrival order.

**Recurrence never drifts.** `next_due_at` is always recomputed from the
original `anchor_time` plus N whole intervals — never from "now" or from
the completion timestamp directly. If you complete a daily task 5 hours
late, the next occurrence is still exactly anchor + 1 day, not
completion-time + 1 day; otherwise a task completed a little late every day
would slowly creep later and later.

**Snooze vs. recurrence.** Snoozing sets `snoozed_until` and bumps the
snooze counters but does **not** touch `next_due_at` — unless the new
snoozed time lands within 15–20 minutes of the already-scheduled
`next_due_at`, in which case they're merged into a single occurrence so the
user doesn't get two near-duplicate reminders minutes apart.

**Cross-device notification dismissal (Step 7).** When a task is marked
`done`, a silent push using the same notification tag
(`task-{id}-{due_at_iso}`) is sent to every *other* registered device, so a
reminder dismissed on your watch also disappears from your phone and laptop.

## Notes / things to wire up for production

- The day-end summary is currently sent as a push payload but not persisted
  to its own table — the spec's schema didn't include a `summaries` table,
  so add one (`summaries: id, user_id, date, summary, highlight, concern,
  tomorrow_suggestion`) if you want history/GET endpoints for past summaries.
- `pick_target_devices` / quiet-hours / escalation logic live in
  `app/services/device_service.py` and `app/workers/reminder_tasks.py` —
  read those two files together to follow the full notification-targeting
  flow end to end.
- VAPID keys are required for real push delivery; without them
  `pywebpush` calls will fail (this is expected and harmless in dev/testing
  without a real subscriber).
- `tests/test_voice_fixtures.py` has a live-API test class that's skipped
  automatically unless `GROQ_API_KEY` is set in the test environment —
  run it explicitly once you have a key to validate real model output
  against the fixtures, not just their shape.

## All commands you'll need

See the bottom of the chat response / `COMMANDS.md` for the full list.
