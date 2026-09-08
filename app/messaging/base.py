"""Uniform interface every WhatsApp provider adapter implements.

Business logic never talks to Twilio/Meta directly — it only calls
MessagingProvider.send_message(). Every provider returned by
app.messaging.factory.get_messaging_provider() is wrapped in
RateLimitedMessagingProvider, so rate limiting happens automatically at the
infrastructure layer, not at each call site.
"""

import logging
from abc import ABC, abstractmethod
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.models.message_rate_limit import MessageRateLimitCounter, RateLimitScope

logger = logging.getLogger(__name__)


class MessagingError(RuntimeError):
    pass


class MessagingProvider(ABC):
    provider_name: str = "unknown"

    @abstractmethod
    async def send_message(self, to: str, text: str) -> bool:
        # Intentionally unimplemented — every concrete provider (Twilio,
        # Meta, mock, the rate-limiting wrapper) supplies its own body.
        ...


def _today() -> date:
    return datetime.now(timezone.utc).date()


class RateLimiter:
    """Enforces per-phone, per-hotel, and global daily send limits.

    Counts live in MessageRateLimitCounter, one row per (scope, scope_key,
    day) — only today's rows are ever read or written.
    """

    def __init__(
        self,
        db: Session,
        *,
        per_phone_limit: int,
        per_hotel_limit: int,
        global_limit: int,
    ):
        self._db = db
        self._per_phone_limit = per_phone_limit
        self._per_hotel_limit = per_hotel_limit
        self._global_limit = global_limit

    def check_and_increment(self, hotel_id: str, phone: str) -> bool:
        """Return True and increment all three counters if under every
        limit; return False (without incrementing anything) if any one of
        the three is already at or over its configured limit.
        """
        today = _today()
        checks = [
            (RateLimitScope.phone, phone, self._per_phone_limit),
            (RateLimitScope.hotel, hotel_id, self._per_hotel_limit),
            (RateLimitScope.global_, "global", self._global_limit),
        ]

        counters = {scope: self._get_or_create(scope, key, today) for scope, key, _ in checks}

        for scope, _key, limit in checks:
            if counters[scope].count >= limit:
                # Deliberately omit the raw phone number from logs — only
                # the hotel and which limit tripped, to stay consistent
                # with the PII-minimization principle.
                logger.warning(
                    "WhatsApp send blocked by rate limit: hotel_id=%s scope=%s limit=%s",
                    hotel_id,
                    scope.value,
                    limit,
                )
                return False

        for scope, _key, _limit in checks:
            counters[scope].count += 1
        self._db.commit()
        return True

    def _get_or_create(
        self, scope: RateLimitScope, scope_key: str, day: date
    ) -> MessageRateLimitCounter:
        row = (
            self._db.query(MessageRateLimitCounter)
            .filter_by(scope=scope, scope_key=scope_key, day=day)
            .one_or_none()
        )
        if row is None:
            row = MessageRateLimitCounter(scope=scope, scope_key=scope_key, day=day, count=0)
            self._db.add(row)
        return row


class RateLimitedMessagingProvider(MessagingProvider):
    """Wraps a concrete MessagingProvider, enforcing RateLimiter before every send."""

    def __init__(self, wrapped: MessagingProvider, rate_limiter: RateLimiter, hotel_id: str):
        self._wrapped = wrapped
        self._rate_limiter = rate_limiter
        self._hotel_id = hotel_id
        self.provider_name = wrapped.provider_name

    async def send_message(self, to: str, text: str) -> bool:
        if not self._rate_limiter.check_and_increment(hotel_id=self._hotel_id, phone=to):
            return False
        return await self._wrapped.send_message(to, text)
