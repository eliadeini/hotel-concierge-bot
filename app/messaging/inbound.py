"""Provider-agnostic inbound-message processing, shared by every webhook
handler (see app/messaging/webhook_base.py) once they've resolved a raw
request down to an InboundMessage.
"""

import logging

from sqlalchemy.orm import Session

from app.api.chat import answer_question
from app.db import SessionLocal
from app.engines import factory as engine_factory
from app.knowledge.markdown_source import MarkdownFileSource
from app.messaging import factory as messaging_factory
from app.messaging.flow import FLOW, FlowOption
from app.models.guest_session import GuestSession
from app.models.hotel_settings import HotelSettings, PresentationMode

logger = logging.getLogger(__name__)

_markdown_source = MarkdownFileSource()

# Deterministic substitutions applied only for PresentationMode.website
# tenants (see gather_context below) — shared knowledge files are written
# from a specific hotel's perspective (e.g. walking distances "from Hotel
# H34"), which is correct for that hotel's own tenant but must not leak to
# a general public site. Ordered longest-pattern-first so "ממלון H34"
# doesn't get double-substituted after "H34" alone already matched.
_LANDMARK_NEUTRALIZATIONS = [
    ("ממלון H34", "ממרכז העיר"),
    ("מלון H34", "מרכז העיר"),
    ("H34", "מרכז העיר"),
]


def _neutralize_landmarks(text: str) -> str:
    for pattern, replacement in _LANDMARK_NEUTRALIZATIONS:
        text = text.replace(pattern, replacement)
    return text


def gather_context(hotel: HotelSettings) -> tuple[str, str]:
    """Merge knowledge-base context across ALL of the hotel's region tags
    (see HotelRegionTag), not just the first match — a hotel's tag list
    mixes specific and broader tags (e.g. "nahariya" and "coast"), and
    relevant local knowledge may exist under more than one of them.

    Each tag's content is labeled with a "## Region: {tag}" heading so the
    model can tell which knowledge came from which region, instead of one
    undifferentiated blob.

    Returns (region_label, combined_context) — region_label is a
    human-readable record of which tags contributed, stored on the
    ConversationLog entry only (not used for lookup itself).

    Public (not underscore-prefixed): also used directly by
    app/ui/routes.py, the browser-based WhatsApp-lookalike demo, so it
    gets exactly the same knowledge-base context a real WhatsApp message
    would.
    """
    tags = [t.tag for t in hotel.region_tags]
    parts = []
    for tag in tags:
        text = _markdown_source.get_context(hotel.hotel_id, tag)
        if text:
            parts.append(f"## Region: {tag}\n{text}")
    combined_context = "\n\n".join(parts)
    if hotel.presentation_mode == PresentationMode.website:
        combined_context = _neutralize_landmarks(combined_context)
    region_label = ",".join(tags)[:64]
    return region_label, combined_context


def _match_flow_option(step, text: str) -> FlowOption | None:
    stripped = text.strip()
    for option in step.options:
        if any(m in stripped for m in option.matches):
            return option
    return None


async def _handle_flow_reply(hotel_id: str, guest: GuestSession, text: str, db: Session) -> None:
    """Continues the scripted onboarding flow (see app/messaging/flow.py)
    for a guest with an active flow_state — never touches the AI engine.
    """
    step = FLOW[guest.flow_state]
    option = _match_flow_option(step, text)
    provider = messaging_factory.get_messaging_provider(hotel_id, db)

    if option is None:
        # Unrecognized reply: flow_state is left unchanged, so the guest
        # stays on the same question and can retry.
        await provider.send_message(guest.phone, step.unrecognized_reply)
        return

    for attr, value in option.record.items():
        setattr(guest, attr, value)
    guest.flow_state = option.next_state
    db.commit()

    if option.next_state is not None:
        await provider.send_message(guest.phone, FLOW[option.next_state].question)
    elif option.ack:
        await provider.send_message(guest.phone, option.ack)
    # option.next_state is None here: the row's flow_state is now None (but
    # the row itself isn't deleted). The GUEST'S NEXT message is a separate
    # process_inbound_message call that re-queries GuestSession fresh —
    # `guest.flow_state is not None` will be False, so it falls straight
    # through to the normal AI-engine chat path below, unchanged. The
    # message that ended the flow (this one) is NOT itself sent to the AI
    # engine — it only gets this ack.


async def process_inbound_message(hotel_id: str, from_number: str, question: str) -> None:
    """Answers a WhatsApp message (from any provider) and sends the reply
    back.

    Runs as a background task with its own DB session — the request's
    Depends(get_db) session may already be closed by the time this runs.
    """
    db = SessionLocal()
    try:
        hotel = db.query(HotelSettings).filter_by(hotel_id=hotel_id).one_or_none()
        if hotel is None:
            return

        # Active flow_state routes to the scripted flow instead of the AI
        # engine; flow_state is None (never started, or just ended above)
        # falls through to the normal chat path unchanged.
        guest = (
            db.query(GuestSession)
            .filter_by(hotel_settings_id=hotel.id, phone=from_number)
            .one_or_none()
        )
        if guest is not None and guest.flow_state is not None:
            await _handle_flow_reply(hotel_id, guest, question, db)
            return

        region_label, context = gather_context(hotel)
        try:
            result = answer_question(
                hotel_id, region_label, question, context, db, engine_factory.get_engine
            )
        except engine_factory.UnknownHotelError:
            return

        provider = messaging_factory.get_messaging_provider(hotel_id, db)
        await provider.send_message(from_number, result.text)
    except Exception:
        # Background tasks fail silently otherwise — never let an
        # exception here surface to the guest, but don't lose it either.
        logger.exception("Failed to process inbound WhatsApp message for hotel_id=%s", hotel_id)
    finally:
        db.close()