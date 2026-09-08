"""Uniform interface every inbound WhatsApp webhook handler implements.

Meta and Twilio send fundamentally different request shapes (JSON vs
form-encoded) and sign them differently, so there's no single generic
parser — each provider gets its own router (see
app/api/meta_whatsapp_webhook.py and app/api/twilio_whatsapp_webhook.py).
Both funnel into the same provider-agnostic processing in
app/messaging/inbound.py once they've resolved a raw request down to an
InboundMessage.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from fastapi import Request, Response
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class InboundMessage:
    hotel_id: str
    from_number: str
    text: str


class WhatsAppWebhookHandler(ABC):
    provider_name: str = "unknown"

    def verify_get(self, request: Request) -> Response:
        """Handle the provider's GET verification handshake. Default: not
        supported (e.g. Twilio has no such step) — override where needed
        (Meta's hub.verify_token/hub.challenge handshake).
        """
        raise NotImplementedError(f"{self.provider_name} has no GET verification handshake")

    @abstractmethod
    async def parse_inbound(self, request: Request, db: Session) -> InboundMessage | None:
        """Validate the request's signature, resolve which hotel it
        belongs to, and extract the message. Raises HTTPException(403) for
        an invalid signature or HTTPException(404) for an unresolvable
        hotel — mirrors the previous single-file behavior. Returns None for
        a valid request that carries no guest message to process (e.g. a
        Meta delivery-status callback).
        """
        ...