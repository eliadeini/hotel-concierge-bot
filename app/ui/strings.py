"""Chrome text for app/ui/templates/website.html, keyed by language.

Not hotel-specific content — that's HotelWebPage's display_name/tagline/
page_title (app/models/hotel_web_page.py). This is the shared UI copy
around it: the input placeholder, accessibility label, send button, error
messages, footer links, and the logo alt-text prefix. Consumed by
_render_website_page() in app/ui/routes.py.
"""

UI_STRINGS: dict[str, dict[str, str]] = {
    "he": {
        "question_label": "שאלה לצ'אטבוט",
        "placeholder": "הקלד/י שאלה...",
        "send_aria_label": "שלח הודעה",
        "send_title": "שלח",
        "error_no_answer": "שגיאה: לא הצלחתי לקבל תשובה כרגע.",
        "error_network": "שגיאת רשת — לא הצלחתי להתחבר לשרת.",
        "footer_accessibility": "הצהרת נגישות",
        "footer_privacy": "מדיניות פרטיות",
        "footer_terms": "תנאי שימוש",
        "logo_alt_prefix": "לוגו",
    },
    "en": {
        "question_label": "Question for the chatbot",
        "placeholder": "Type a question...",
        "send_aria_label": "Send message",
        "send_title": "Send",
        "error_no_answer": "Error: couldn't get an answer right now.",
        "error_network": "Network error — couldn't connect to the server.",
        "footer_accessibility": "Accessibility Statement",
        "footer_privacy": "Privacy Policy",
        "footer_terms": "Terms of Use",
        "logo_alt_prefix": "Logo",
    },
}
