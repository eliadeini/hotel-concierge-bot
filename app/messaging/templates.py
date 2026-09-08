"""Fallback WhatsApp text for hotels with no skill file.

See app/knowledge/hotel_skill.py — HotelSettings.hotel_skill_path points to
a per-hotel Markdown file that overrides this greeting. This is only what's
used when a hotel has no skill file configured yet.
"""

DEFAULT_GREETING = (
    "ברוך הבא! אנו שמחים לארח אותך. אני הצ'אט בוט של המלון, אלווה אותך "
    "ואעזור לך לתכנן את החופשה ואת הביקור. אתה מוזמן להתייעץ איתי."
)