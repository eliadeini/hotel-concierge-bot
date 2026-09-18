"""FastAPI routes for the WhatsApp-lookalike browser demo.

Reuses the exact same context-gathering and AI-answering logic the real
WhatsApp path uses (app.messaging.inbound.gather_context,
app.api.chat.answer_question) — this is not a separate/divergent
implementation, so what's shown here is provably what a real WhatsApp
message would get. See README.md in this folder for why this exists.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.chat import ChatResponse, answer_question
from app.config import UIMode, settings
from app.db import get_db
from app.engines import factory as engine_factory
from app.messaging.inbound import gather_context
from app.models.hotel_settings import HotelSettings

router = APIRouter()

# Hardcoded tenants for now — the first thing to generalize (e.g. a
# ?hotel_id= / path param) once this grows to serve more than one hotel or
# more than one location. DEMO_HOTEL_ID (PresentationMode.hotel_demo) backs
# the WhatsApp-lookalike hotel demo; NAHARIYA_GUIDE_HOTEL_ID
# (PresentationMode.website) is a separate tenant backing the general
# public site — kept separate specifically so shared knowledge content can
# be neutralized for the public tenant without affecting the hotel demo
# (see app/messaging/inbound.py::gather_context).
DEMO_HOTEL_ID = "hotel-demo"
NAHARIYA_GUIDE_HOTEL_ID = "nahariya-guide"

_DEMO_HTML = (Path(__file__).parent / "templates" / "demo.html").read_text(encoding="utf-8")
_WEBSITE_HTML = (Path(__file__).parent / "templates" / "website.html").read_text(encoding="utf-8")


class DemoAskRequest(BaseModel):
    question: str = Field(min_length=1)


def _ask(hotel_id: str, question: str, db: Session) -> ChatResponse:
    """Shared by both browser ask endpoints below — hotel lookup,
    gather_context, answer_question, mirroring
    app.messaging.inbound.process_inbound_message's sequence but stopping
    short of the WhatsApp-provider send step and returning the text
    directly instead.

    Deliberately skips GuestSession/flow_state routing (app/messaging/flow.py):
    there's no "checked in via WhatsApp" concept for a browser page, so this
    always goes straight to the AI-engine path.
    """
    hotel = db.query(HotelSettings).filter_by(hotel_id=hotel_id).one_or_none()
    if hotel is None:
        raise HTTPException(
            status_code=503,
            detail=f"Tenant {hotel_id!r} not seeded — see app/ui/README.md",
        )

    region_label, context = gather_context(hotel)
    try:
        result = answer_question(
            hotel_id, region_label, question, context, db, engine_factory.get_engine
        )
    except engine_factory.UnknownHotelError:
        raise HTTPException(status_code=404, detail="Unknown hotel_id")

    return ChatResponse(text=result.text, found_in_kb=result.found_in_kb)


@router.get("/demo", response_class=HTMLResponse)
def demo_page() -> str:
    """Always the hotel-lookalike look, regardless of UIMode — kept
    reachable on its own fixed path for demoing to prospective hotel
    clients even while the site's default (GET /) is in website mode."""
    return _DEMO_HTML


@router.get("/chatbot/nahariya", response_class=HTMLResponse)
def nahariya_chatbot_page() -> str:
    """The general public website look for Nahariya. Path is
    location-scoped (/chatbot/<location>) rather than a flat /website so
    other locations can get their own page later (/chatbot/eilat, etc.)
    without reshuffling this one's URL."""
    return _WEBSITE_HTML


@router.get("/", include_in_schema=False)
def index_page() -> RedirectResponse:
    """Redirect target is config-driven (settings.ui_mode), so the same
    deployment can be flipped between "general public website" and "hotel
    demo" as its default front door without a code change. /demo and
    /chatbot/nahariya are both reachable directly either way."""
    target = "/chatbot/nahariya" if settings.ui_mode == UIMode.website else "/demo"
    return RedirectResponse(url=target)


@router.post("/demo/ask", response_model=ChatResponse)
def demo_ask(req: DemoAskRequest, db: Session = Depends(get_db)) -> ChatResponse:
    return _ask(DEMO_HOTEL_ID, req.question, db)


@router.post("/chatbot/nahariya/ask", response_model=ChatResponse)
def nahariya_chatbot_ask(req: DemoAskRequest, db: Session = Depends(get_db)) -> ChatResponse:
    return _ask(NAHARIYA_GUIDE_HOTEL_ID, req.question, db)