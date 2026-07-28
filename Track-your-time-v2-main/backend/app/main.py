from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# from app.api import auth, tasks, voice, devices, summary, companion
from app.api import auth, tasks, voice, devices, summary, companion, activities
from app.config import settings
from app.websocket import routes as ws_routes

app = FastAPI(title="Smart Reminder")

_cors_origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]

# Fail fast rather than serving an API no browser can reach. A forgotten
# CORS_ORIGINS in production shows up client-side as an opaque "Network Error"
# that is indistinguishable from the backend being down — hours of debugging
# for a missing env var.
if settings.ENVIRONMENT != "development" and any("localhost" in o for o in _cors_origins):
    raise RuntimeError(
        "CORS_ORIGINS still contains the localhost default in a non-development "
        f"environment (ENVIRONMENT={settings.ENVIRONMENT!r}). Set it to the deployed "
        "frontend origin(s), comma-separated, with no trailing slash."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(voice.router)
app.include_router(devices.router)
app.include_router(summary.router)
app.include_router(companion.router)
app.include_router(activities.router)
app.include_router(ws_routes.router)
# Developer tools — only available in development mode.
if settings.ENVIRONMENT == "development":
    from app.api import dev
    app.include_router(dev.router)
@app.get("/health")
async def health():
    return {"status": "ok"}
