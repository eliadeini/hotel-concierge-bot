import logging
import secrets
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.engines import factory
from app.engines.base import EngineResponse
from app.engines.factory import UnknownHotelError
from app.knowledge.base import KnowledgeSource
from app.knowledge.hotel_skill import read_hotel_skill
from app.knowledge.markdown_source import MarkdownFileSource
from app.messaging import factory as messaging_factory
from app.messaging.flow import HELP_QUESTION
from app.messaging.templates import DEFAULT_GREETING
from app.models.conversation_log import ConversationLog
from app.models.guest_session import GuestFlowState, GuestSession
from app.models.hotel_settings import AIEngineType, HotelSettings
from app.prompts import build_system_prompt
from app.security.crypto import encrypt_key


logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

router = APIRouter()

_markdown_source = MarkdownFileSource()


def get_knowledge_source() -> KnowledgeSource:
    return _markdown_source


def get_engine_factory():
    return factory.get_engine


class ChatRequest(BaseModel):
    hotel_id: str = Field(min_length=1)
    region: str = Field(min_length=1)
    question: str = Field(min_length=1)


class ChatResponse(BaseModel):
    # Deliberately excludes raw_provider_response — that field is internal
    # debug data and must never reach clients.
    text: str
    found_in_kb: bool


def answer_question(
    hotel_id: str,
    region: str,
    question: str,
    context: str,
    db: Session,
    engine_factory,
) -> EngineResponse:
    """Core chat logic — shared by the /chat endpoint, the WhatsApp webhook
    handlers, and the browser demo (app/ui/routes.py). Callers build
    `context` themselves (a single region's knowledge for /chat, merged
    multi-tag knowledge for WhatsApp/demo — see
    app/messaging/inbound.py::gather_context) so this function doesn't need
    to know how context was gathered. `region` is stored on the log entry
    only. Raises UnknownHotelError for an unknown hotel_id."""
    engine = engine_factory(hotel_id, db)

    system_prompt = build_system_prompt()
    hotel = db.query(HotelSettings).filter_by(hotel_id=hotel_id).one_or_none()
    skill = read_hotel_skill(hotel.hotel_skill_path) if hotel else None
    if skill:
        system_prompt = f"{system_prompt}\n\n<hotel_instructions>\n{skill}\n</hotel_instructions>"

    # Only emitted when LOG_LEVEL=DEBUG (see app/config.py) — the exact
    # request sent to the AI engine, for prompt-tuning/debugging. Never
    # returned in any API response.
    logger.debug(
        "AI request hotel_id=%s\n--- system_prompt ---\n%s\n--- context ---\n%s\n"
        "--- question ---\n%s",
        hotel_id,
        system_prompt,
        context,
        question,
    )

    result = engine.ask(
        system_prompt=system_prompt,
        context=context,
        question=question,
    )

    # Anonymous log: question, answer, found_in_kb — no guest identifiers.
    db.add(
        ConversationLog(
            hotel_id=hotel_id,
            region=region,
            question=question,
            answer=result.text,
            found_in_kb=result.found_in_kb,
            ai_engine=engine.provider_name,
        )
    )
    db.commit()
    return result


@router.post("/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    db: Session = Depends(get_db),
    source: KnowledgeSource = Depends(get_knowledge_source),
    engine_factory=Depends(get_engine_factory),
) -> ChatResponse:
    context = source.get_context(req.hotel_id, req.region)
    try:
        result = answer_question(
            req.hotel_id, req.region, req.question, context, db, engine_factory
        )
    except UnknownHotelError:
        raise HTTPException(status_code=404, detail="Unknown hotel_id")

    return ChatResponse(text=result.text, found_in_kb=result.found_in_kb)


class HotelUpsertRequest(BaseModel):
    hotel_id: str = Field(min_length=1, max_length=64)
    ai_engine: AIEngineType
    api_key: str = Field(min_length=1)
    is_test: bool = False
    hotel_skill_path: str | None = None


@router.post("/admin/hotels")
def upsert_hotel(
    req: HotelUpsertRequest,
    x_admin_token: str = Header(default=""),
    db: Session = Depends(get_db),
) -> dict:
    """Minimal admin endpoint (no UI in phase 1): create/update a hotel's
    engine choice and API key. The key is encrypted at rest and never echoed."""
    if not settings.admin_token:
        raise HTTPException(status_code=503, detail="Admin endpoint not configured")
    if not secrets.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(status_code=401, detail="Invalid admin token")

    row = db.query(HotelSettings).filter_by(hotel_id=req.hotel_id).one_or_none()
    if row is None:
        row = HotelSettings(hotel_id=req.hotel_id)
        db.add(row)
    row.ai_engine = req.ai_engine
    row.api_key_encrypted = encrypt_key(req.api_key)
    row.is_test = req.is_test
    row.hotel_skill_path = req.hotel_skill_path
    db.commit()

    return {
        "hotel_id": row.hotel_id,
        "ai_engine": row.ai_engine.value,
        "is_test": row.is_test,
        "hotel_skill_path": row.hotel_skill_path,
    }


def get_messaging_provider_factory():
    return messaging_factory.get_messaging_provider


class GuestCheckinRequest(BaseModel):
    phone: str = Field(min_length=1, max_length=32)
    check_in: date | None = None
    check_out: date | None = None


@router.post("/admin/hotels/{hotel_id}/guests")
async def checkin_guest(
    hotel_id: str,
    req: GuestCheckinRequest,
    x_admin_token: str = Header(default=""),
    db: Session = Depends(get_db),
    provider_factory=Depends(get_messaging_provider_factory),
) -> dict:
    """Registers a guest's stay and immediately sends the WhatsApp
    onboarding greeting (see app/messaging/flow.py), starting the scripted
    yes/no + trip-type flow that app/api/whatsapp_webhook.py continues when
    the guest replies."""
    if not settings.admin_token:
        raise HTTPException(status_code=503, detail="Admin endpoint not configured")
    if not secrets.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(status_code=401, detail="Invalid admin token")

    hotel = db.query(HotelSettings).filter_by(hotel_id=hotel_id).one_or_none()
    if hotel is None:
        raise HTTPException(status_code=404, detail="Unknown hotel_id")

    row = (
        db.query(GuestSession)
        .filter_by(hotel_settings_id=hotel.id, phone=req.phone)
        .one_or_none()
    )
    if row is None:
        row = GuestSession(hotel_settings_id=hotel.id, phone=req.phone)
        db.add(row)
    row.check_in = req.check_in or date.today()
    row.check_out = req.check_out
    # Reset in case this is a returning guest reusing an old row.
    row.welcome_sent_at = None
    row.flow_state = None
    row.trip_type = None

    greeting = read_hotel_skill(hotel.hotel_skill_path) or DEFAULT_GREETING
    message = f"{greeting}\n\n{HELP_QUESTION}"

    provider = provider_factory(hotel_id, db)
    sent = await provider.send_message(req.phone, message)
    if sent:
        row.welcome_sent_at = _utcnow()
        row.flow_state = GuestFlowState.awaiting_help_confirmation
    db.commit()

    return {
        "hotel_id": hotel_id,
        "phone": row.phone,
        "check_in": row.check_in.isoformat(),
        "check_out": row.check_out.isoformat() if row.check_out else None,
        "welcome_sent": sent,
    }
