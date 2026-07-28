# How to deploy this app

## First, understand what you're deploying

Most apps are one thing you upload. **This app is 5 things that must all run together.**

Think of it like a restaurant:

| Piece | Restaurant analogy | What happens if it's missing |
|---|---|---|
| **Postgres** | the fridge (stores everything) | nothing works |
| **Redis** | the order spike / ticket rail | login gets slower; notifications stop |
| **API** | the waiter (talks to your app) | website can't load anything |
| **Celery beat** | the alarm clock | **no reminders ever fire** |
| **Celery worker** | the cook | **no notification is ever delivered** |
| **Frontend** | the dining room | nothing to look at |

**The last two are the ones people forget.** They fail *silently* — your app looks completely fine, returns success, and simply never notifies you. This is exactly why your hourly reminders weren't arriving earlier: beat wasn't running.

**Beat rings the alarm. Worker actually cooks. You need both.**

---

## Where each piece goes

- **Railway** hosts pieces 1–5 (database, redis, API, beat, worker)
- **Vercel** hosts piece 6 (the website)

---

# PART 1 — Railway

## Step 1: Create the project and add the database

1. Go to railway.app → **New Project**
2. Click **+ New** → **Database** → **Add PostgreSQL**
3. Click **+ New** → **Database** → **Add Redis**

That's pieces 1 and 2 done. No configuration needed yet.

## Step 2: Understand which URL to use

Railway does **not** show a variable called "internal URL". It gives you two, and the names are misleading:

| Variable on the Postgres service | What it actually is |
|---|---|
| `DATABASE_URL` | 🟢 **internal** — contains `postgres.railway.internal`. **Use this one.** |
| `DATABASE_PUBLIC_URL` | 🔴 public proxy — contains `proxy.rlwy.net`. Avoid. |

Click the 👁 icon next to `DATABASE_URL` to confirm you see `.railway.internal`.

> **Why this matters a lot:** I measured the public proxy at **486 ms per database query**. Your app makes 3–11 queries per click, so using it would make every page take ~2 seconds. Internal traffic never leaves Railway and is roughly 1000× faster.

Redis works the same way — its `REDIS_URL` is already the internal one.

### Don't copy-paste the values — use references

Instead of pasting the actual URL into your backend service, use Railway's reference syntax so the link survives credential rotation:

```
DATABASE_URL           = ${{Postgres.DATABASE_URL}}
REDIS_URL              = ${{Redis.REDIS_URL}}
CELERY_BROKER_URL      = ${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND  = ${{Redis.REDIS_URL}}
```

(Use whatever your Postgres/Redis services are actually named — Railway autocompletes them.)

**You do not need to add `+asyncpg` yourself.** Railway hands out `postgresql://`, and `app/config.py` now rewrites it to `postgresql+asyncpg://` automatically (it also handles the legacy `postgres://` spelling). This used to be a manual edit that broke on every rotation and produced a confusing "dialect is not async" crash when forgotten.

## Step 3: Create the API service

1. **+ New** → **GitHub Repo** → pick your repo
2. Open **Settings** → set **Root Directory** to `backend`
3. Go to **Variables** and paste in everything from the table below
4. Go to **Settings → Networking** → **Generate Domain**

You now have a public URL like `https://something.up.railway.app`. Save it.

### Variables to set

| Variable | What to put |
|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` |
| `CELERY_BROKER_URL` | `${{Redis.REDIS_URL}}` |
| `CELERY_RESULT_BACKEND` | `${{Redis.REDIS_URL}}` |
| `JWT_SECRET_KEY` | a long random string (make a new one) |
| `GROQ_API_KEY` | your Groq key |
| `VAPID_PUBLIC_KEY` | your existing public key |
| `VAPID_PRIVATE_KEY` | your existing private key |
| `VAPID_CLAIMS_SUB` | `mailto:you@example.com` |
| `CORS_ORIGINS` | leave blank for now — you'll fill it in Part 3 |
| `ENVIRONMENT` | `production` |

You don't upload any `.env` file. Railway's Variables tab replaces it.

## Step 4: Create the worker (the cook)

1. **+ New** → **GitHub Repo** → **the same repo again**
2. **Settings** → **Root Directory** = `backend`
3. **Settings** → **Custom Start Command**:
   ```
   celery -A app.workers.celery_app worker --loglevel=info
   ```
4. **Variables** → paste the **exact same variables** as Step 3
5. Do **not** generate a domain — this one is internal

> If you're on Windows locally you use `--pool=solo`. **Do not use that here.** Railway runs Linux, where the default is correct and faster.

## Step 5: Create beat (the alarm clock)

Exactly like Step 4, but the start command is:

```
celery -A app.workers.celery_app beat --loglevel=info
```

Same variables again. No domain.

> **Only ever run ONE beat.** Keep this service at 1 replica. Two alarm clocks means every reminder fires twice.

---

# PART 2 — Vercel (the website)

1. vercel.com → **Add New** → **Project** → pick the same repo
2. Set **Root Directory** to `frontend`
3. Framework preset: **Vite** (usually auto-detected)
4. Add two Environment Variables:

| Variable | Value |
|---|---|
| `VITE_API_URL` | your Railway URL from Step 3 — **no slash at the end** |
| `VITE_VAPID_PUBLIC_KEY` | the same public key you used on Railway |

5. **Deploy**

> **Important:** these get baked into the built files. If you change them later you must **redeploy** — editing the value alone does nothing.
>
> The `VAPID_PUBLIC_KEY` must be **identical** on Railway and Vercel. If they differ, notifications silently never register.

---

# PART 3 — Connect the two (don't skip this)

Vercel gave you a URL like `https://your-app.vercel.app`.

Go back to **Railway → API service → Variables** and set:

```
CORS_ORIGINS=https://your-app.vercel.app
```

No trailing slash. Then redeploy the API.

> Without this, your website loads but every action fails with "Network Error".
>
> The app has a safety net here: if `ENVIRONMENT=production` and `CORS_ORIGINS` still says `localhost`, **the API refuses to start**. That's on purpose — a loud crash is much easier to debug than a mysterious browser error.

---

# PART 4 — Check it actually works

Do these in order. Step 5 is the important one.

1. Visit `https://your-api.up.railway.app/health` → should say ok
2. Open your Vercel site, sign up, log in
3. Create a task → if this works, database + API + CORS are all correct
4. Open the **worker** logs → should say `celery@... ready.`
5. Open the **beat** logs → within 1 minute should say `Scheduler: Sending due task...`
6. Allow notifications in your browser, then trigger a test push → **a real notification should appear**

**Step 6 is the only test that proves the worker is running.** Everything else can pass while notifications are quietly broken.

---

# Running locally vs live (this is now easy)

You have two files on each side:

```
.env         →  live settings (Railway)
.env.local   →  your computer's settings  ← this one wins
```

**That's the whole system.** `.env.local` beats `.env`.

| What you want | What you do |
|---|---|
| Work on your computer | Keep `.env.local`. Done. |
| Test against the live server | Rename `.env.local` to `.env.local.off`, restart |
| Go back to local | Rename it back |
| Deploy | Nothing — Railway/Vercel variables override both files |

No editing code. No commenting lines out. Same idea on backend and frontend.

---

# Before you go live: rotate your secrets

The passwords and keys currently in your `.env` have been sitting on your dev machine. Generate new ones for production:

- `JWT_SECRET_KEY` — new random string (this logs everyone out, which is fine)
- Database password
- `GROQ_API_KEY`

Keep the **VAPID keys the same** — changing those disconnects every device that already subscribed to notifications.

All `.env` files are already gitignored, so nothing secret gets pushed to GitHub.

---

# Speed you can expect

Measured after the optimisation work:

| Action | Before | Now |
|---|---|---|
| Health check | 218 ms | 3 ms |
| Load your tasks | ~2.1 s | 14 ms |
| Mark a task done | ~5 s | 20 ms |

You'll get similar numbers on Railway **as long as you use the internal database URL** from Step 2. Using the public proxy instead puts you back at the "Before" column — it's the single most expensive mistake available here.

---

# Common problems

| Symptom | Cause |
|---|---|
| Site loads, everything fails | `CORS_ORIGINS` not set to your Vercel URL (Part 3) |
| No reminders at all | beat service not running |
| Reminders logged but no notification appears | worker service not running |
| Every reminder arrives twice | two beat services running |
| Notifications never register | VAPID public key differs between Railway and Vercel |
| Everything is slow | using the `proxy.rlwy.net` URL instead of `.railway.internal` |
| API won't start | `CORS_ORIGINS` still contains `localhost` while `ENVIRONMENT=production` |

One more: if the worker/beat services are allowed to **sleep when idle**, your reminders stop. They need to stay awake.
