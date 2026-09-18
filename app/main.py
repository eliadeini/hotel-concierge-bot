import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.chat import router
from app.api.meta_whatsapp_webhook import router as meta_whatsapp_router
from app.api.twilio_whatsapp_webhook import router as twilio_whatsapp_router
from app.config import settings
from app.db import init_db
from app.ui.routes import router as ui_router

# Without this, app.* loggers (e.g. the mock WhatsApp provider) never reach
# the console. Attached directly to the "app" logger, not the root logger —
# uvicorn configures its own root/uvicorn.* logging independently, and
# basicConfig() on root is unreliable relative to that (order-dependent).
# Level is configurable (LOG_LEVEL in .env) — DEBUG additionally logs the
# full AI prompt/context sent on every request, see app/api/chat.py.
_app_logger = logging.getLogger("app")
_app_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
_app_logger.addHandler(logging.StreamHandler())


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Hotel Concierge Bot", lifespan=lifespan)
app.include_router(router)
app.include_router(meta_whatsapp_router)
app.include_router(twilio_whatsapp_router)
app.include_router(ui_router)

# Static assets for the browser UI (background images, etc.) — no build
# step/asset pipeline in this repo, so this is a plain file mount rather
# than anything bundler-driven. See app/ui/README.md.
_STATIC_DIR = Path(__file__).parent / "ui" / "static"
_STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
