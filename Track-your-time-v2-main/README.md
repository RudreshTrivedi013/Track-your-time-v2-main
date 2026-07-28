# SmartReminder

SmartReminder is a full-stack reminder and productivity check-in app.

- Frontend: React, Vite, TypeScript, Tailwind CSS
- Backend: FastAPI, PostgreSQL, Redis, Celery, Alembic
- Notifications: Web Push with VAPID keys
- AI: Groq-backed voice parsing and productivity companion features

## Project Structure

```text
backend/   FastAPI API, Celery workers, database models, migrations
frontend/  React app and service worker
```

## Required Environment

Create `backend/.env` from `backend/.env.example` and set production values:

```env
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://...
CELERY_BROKER_URL=redis://...
CELERY_RESULT_BACKEND=redis://...
JWT_SECRET_KEY=change-this-to-a-long-random-secret
GROQ_API_KEY=your-groq-api-key
VAPID_PUBLIC_KEY=your-vapid-public-key
VAPID_PRIVATE_KEY=your-vapid-private-key
VAPID_CLAIMS_SUB=mailto:you@example.com
CORS_ORIGINS=https://your-frontend-domain.example
ENVIRONMENT=production
```

Create `frontend/.env.local` from `frontend/.env.example`:

```env
VITE_API_URL=https://your-backend-domain.example
VITE_VAPID_PUBLIC_KEY=your-vapid-public-key
```

## Local Development

Backend:

```powershell
cd backend
docker compose up --build
docker compose exec backend alembic upgrade head
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

## Checks

Frontend production build:

```powershell
cd frontend
npm.cmd run build
```

Backend focused test:

```powershell
cd backend
$env:DATABASE_URL='sqlite+aiosqlite:///dummy.db'
$env:TEST_DATABASE_URL='sqlite+aiosqlite:///test.db'
$env:JWT_SECRET_KEY='dev-only'
$env:GROQ_API_KEY='dev-only'
.\venv\Scripts\python.exe -m pytest tests\test_checkin_service.py
```

## GitHub Deployment Notes

Do not commit `.env`, `.env.local`, `node_modules`, `dist`, virtualenvs, Celery beat files, or local notes. The root `.gitignore` is configured for those.

Before deploying, rotate any secrets that were used locally and configure them in your hosting provider's environment variable settings.
