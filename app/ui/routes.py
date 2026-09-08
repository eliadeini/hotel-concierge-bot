"""FastAPI routes for the WhatsApp-lookalike browser demo.

Reuses the exact same context-gathering and AI-answering logic the real
WhatsApp path uses (app.messaging.inbound.gather_context,
app.api.chat.answer_question) — this is not a separate/divergent
implementation, so what's shown here is provably what a real WhatsApp
message would get. See README.md in this folder for why this exists.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.chat import ChatResponse, answer_question
from app.db import get_db
from app.engines import factory as engine_factory
from app.messaging.inbound import gather_context
from app.models.hotel_settings import HotelSettings

router = APIRouter()

# The only hotel currently seeded in the local dev DB. Hardcoded for now —
# the first thing to generalize (e.g. a ?hotel_id= param) once this grows
# from "demo for the pilot hotel" into a real guest-facing widget for
# multiple hotels.
DEMO_HOTEL_ID = "hotel-demo"

_DEMO_HTML = (Path(__file__).parent / "templates" / "demo.html").read_text(encoding="utf-8")


class DemoAskRequest(BaseModel):
    question: str = Field(min_length=1)


@router.get("/demo", response_class=HTMLResponse)
def demo_page() -> str:
    return _DEMO_HTML


@router.post("/demo/ask", response_model=ChatResponse)
def demo_ask(req: DemoAskRequest, db: Session = Depends(get_db)) -> ChatResponse:
    """Mirrors app.messaging.inbound.process_inbound_message's sequence —
    hotel lookup, gather_context, answer_question — but stops short of the
    WhatsApp-provider send step and returns the text directly instead.

    Deliberately skips GuestSession/flow_state routing (app/messaging/flow.py):
    there's no "checked in via WhatsApp" concept for a browser page, so this
    always goes straight to the AI-engine path.
    """
    hotel = db.query(HotelSettings).filter_by(hotel_id=DEMO_HOTEL_ID).one_or_none()
    if hotel is None:
        raise HTTPException(
            status_code=503,
            detail=f"Demo hotel {DEMO_HOTEL_ID!r} not seeded — see app/ui/README.md",
        )

    region_label, context = gather_context(hotel)
    try:
        result = answer_question(
            DEMO_HOTEL_ID, region_label, req.question, context, db, engine_factory.get_engine
        )
    except engine_factory.UnknownHotelError:
        raise HTTPException(status_code=404, detail="Unknown hotel_id")

    return ChatResponse(text=result.text, found_in_kb=result.found_in_kb)