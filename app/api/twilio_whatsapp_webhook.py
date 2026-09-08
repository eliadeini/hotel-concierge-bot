"""Twilio WhatsApp webhook: inbound message form payloads, signed via
X-Twilio-Signature (a per-hotel auth token, unlike Meta's app-wide secret).

Not currently live-configured in Twilio's console — the free Sandbox
approach was abandoned (see the project-whatsapp-integration-progress
memory and hotel_concierge_bot_plan.md), so this route lives on a new path
(/webhook/whatsapp/twilio) rather than reusing the Meta-verified
/webhook/whatsapp.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from twilio.request_validator import RequestValidator

from app.config import settings
from app.db import get_db
from app.messaging.inbound import process_inbound_message
from app.messaging.webhook_base import InboundMessage, WhatsAppWebhookHandler
from app.models.hotel_messaging_settings import HotelMessagingSettings
from app.models.hotel_settings import HotelSettings
from app.security.crypto import decrypt_key

logger = logging.getLogger(__name__)

router = APIRouter()


class TwilioWhatsAppWebhookHandler(WhatsAppWebhookHandler):
    provider_name = "twilio"

    async def parse_inbound(self, request: Request, db: Session) -> InboundMessage | None:
        form = await request.form()
        params = {key: str(value) for key, value in form.items()}
        to_number = params.get("To", "")
        from_number = params.get("From", "").removeprefix("whatsapp:")
        body_text = params.get("Body", "")

        hotel_id, auth_token = self._resolve_hotel_and_token(to_number, db)
        if hotel_id is None:
            raise HTTPException(status_code=404, detail="Unknown WhatsApp number")

        signature = request.headers.get("X-Twilio-Signature", "")
        if not RequestValidator(auth_token).validate(str(request.url), params, signature):
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")

        return InboundMessage(hotel_id=hotel_id, from_number=from_number, text=body_text)

    @staticmethod
    def _resolve_hotel_and_token(to_number: str, db: Session) -> tuple[str | None, str]:
        """Match the inbound `To` number to a hotel and the Twilio auth
        token that should validate this request's signature.

        Hotel-specific numbers are matched first. If the inbound number is
        the global default number and exactly one hotel exists, that hotel
        is used — a phase-1 single-tenant simplification; with more than
        one hotel and no hotel-specific number configured, the request
        can't be attributed and is rejected.
        """
        msg = (
            db.query(HotelMessagingSettings)
            .filter_by(twilio_whatsapp_number=to_number)
            .one_or_none()
        )
        if msg is not None:
            auth_token = (
                decrypt_key(msg.twilio_auth_token_encrypted)
                if msg.twilio_auth_token_encrypted
                else settings.twilio_auth_token
            )
            return msg.hotel.hotel_id, auth_token

        if to_number and to_number == settings.twilio_whatsapp_number:
            hotels = db.query(HotelSettings).all()
            if len(hotels) == 1:
                return hotels[0].hotel_id, settings.twilio_auth_token

        return None, ""


_handler = TwilioWhatsAppWebhookHandler()


@router.post("/webhook/whatsapp/twilio")
async def receive_twilio_whatsapp_message(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Response:
    message = await _handler.parse_inbound(request, db)
    if message is not None:
        background_tasks.add_task(
            process_inbound_message, message.hotel_id, message.from_number, message.text
        )
    return Response(status_code=200)