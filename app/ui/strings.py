"""Chrome/content text for app/ui/templates/website.html and about.html,
keyed by language.

Not hotel-specific content — that's HotelWebPage's display_name/tagline/
page_title (app/models/hotel_web_page.py). UI_STRINGS is the shared UI copy
around website.html: the input placeholder, accessibility label, send
button, error messages, footer links, logo alt-text prefix, and the About
button's own label. Consumed by _render_website_page() in
app/ui/routes.py. ABOUT_STRINGS is the /about page's own content, consumed
by _render_about_page() in the same file.
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
        "about_button": "אודות",
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
        "about_button": "About",
    },
}

# Content for app/ui/templates/about.html, keyed by language. bio_html and
# heading are placeholder copy — the user supplies the real text/name
# afterward (see app/ui/README.md's "About page" section); only this dict
# needs editing at that point, not the template or route.
ABOUT_STRINGS: dict[str, dict[str, str]] = {
    "he": {
        "page_title": "אודות",
        "heading": "[placeholder — שם יתעדכן]",
        "photo_alt": "[placeholder — שם יתעדכן]",
        "bio_html": "<p>[placeholder — תוכן אודות יתעדכן]</p>",
        "back_link_text": "חזרה לאתר",
    },
    "en": {
        "page_title": "About",
        "heading": "[placeholder — name pending]",
        "photo_alt": "[placeholder — name pending]",
        "bio_html": "<p>[placeholder — bio content pending]</p>",
        "back_link_text": "Back to site",
    },
}
