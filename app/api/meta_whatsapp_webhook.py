"""Meta WhatsApp Cloud API webhook: GET verification handshake, plus
inbound message JSON payloads signed via X-Hub-Signature-256 (a single
app-wide secret, unlike Twilio's per-hotel signing key).

This is the live-registered route (/webhook/whatsapp) — its GET handshake
has already been verified in Meta's dashboard, so its path is deliberately
unchanged from before the Twilio/Meta split (see the
project-whatsapp-integration-progress memory and hotel_concierge_bot_plan.md).
"""

import hashlib
import hmac
import json
import logging
import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.messaging.inbound import process_inbound_message
from app.messaging.webhook_base import InboundMessage, WhatsAppWebhookHandler
from app.models.hotel_messaging_settings import HotelMessagingSettings
from app.models.hotel_settings import HotelSettings

logger = logging.getLogger(__name__)

router = APIRouter()


class MetaWhatsAppWebhookHandler(WhatsAppWebhookHandler):
    provider_name = "meta_direct"

    def verify_get(self, request: Request) -> Response:
        hub_verify_token = request.query_params.get("hub.verify_token", "")
        hub_challenge = request.query_params.get("hub.challenge", "")
        if not settings.whatsapp_webhook_verify_token or not secrets.compare_digest(
            hub_verify_token, settings.whatsapp_webhook_verify_token
        ):
            raise HTTPException(status_code=403, detail="Invalid verify token")
        return Response(content=hub_challenge, media_type="text/plain")

    async def parse_inbound(self, request: Request, db: Session) -> InboundMessage | None:
        raw_body = await request.body()
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not self._verify_signature(raw_body, signature):
            raise HTTPException(status_code=403, detail="Invalid Meta signature")

        try:
            payload = json.loads(raw_body or b"{}")
        except json.JSONDecodeError:
            payload = {}
        message, phone_number_id = self._extract_message(payload)
        if message is None:
            # Delivery/status callbacks etc. share this endpoint but carry
            # no guest message — not an error, just nothing to process.
            return None

        hotel_id = self._resolve_hotel(phone_number_id, db)
        if hotel_id is None:
            raise HTTPException(status_code=404, detail="Unknown WhatsApp phone_number_id")

        from_number = str(message.get("from", ""))
        text = str(message.get("text", {}).get("body", ""))
        return InboundMessage(hotel_id=hotel_id, from_number=from_number, text=text)

    @staticmethod
    def _verify_signature(raw_body: bytes, signature_header: str) -> bool:
        """Validates Meta's X-Hub-Signature-256 header: HMAC-SHA256 of the
        raw request body, keyed by the App Secret (app-wide, not per-hotel).
        """
        if not settings.meta_app_secret or not signature_header.startswith("sha256="):
            return False
        expected = hmac.new(
            settings.meta_app_secret.encode(), raw_body, hashlib.sha256
        ).hexdigest()
        provided = signature_header.removeprefix("sha256=")
        return hmac.compare_digest(expected, provided)

    @staticmethod
    def _resolve_hotel(phone_number_id: str, db: Session) -> str | None:
        """Hotel-specific numbers are matched first. If the inbound number
        is the global default phone_number_id and exactly one hotel exists,
        that hotel is used — a phase-1 single-tenant simplification; with
        more than one hotel and no hotel-specific number configured, the
        request can't be attributed and is rejected.
        """
        msg = (
            db.query(HotelMessagingSettings)
            .filter_by(meta_phone_number_id=phone_number_id)
            .one_or_none()
        )
        if msg is not None:
            return msg.hotel.hotel_id

        if phone_number_id and phone_number_id == settings.meta_phone_number_id:
            hotels = db.query(HotelSettings).all()
            if len(hotels) == 1:
                return hotels[0].hotel_id

        return None

    @staticmethod
    def _extract_message(payload: dict) -> tuple[dict | None, str]:
        """Meta nests the actual message several levels deep and delivers
        non-message events (e.g. delivery-status callbacks) on the same
        endpoint. Returns (message, phone_number_id); message is None when
        there's no inbound guest message in this payload.
        """
        try:
            value = payload["entry"][0]["changes"][0]["value"]
        except (KeyError, IndexError, TypeError):
            return None, ""
        phone_number_id = str(value.get("metadata", {}).get("phone_number_id", ""))
        messages = value.get("messages")
        if not messages:
            return None, phone_number_id
        return messages[0], phone_number_id


_handler = MetaWhatsAppWebhookHandler()


@router.get("/webhook/whatsapp")
def verify_meta_webhook(request: Request) -> Response:
    return _handler.verify_get(request)


@router.post("/webhook/whatsapp")
async def receive_meta_whatsapp_message(
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