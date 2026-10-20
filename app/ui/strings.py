"""Chrome/content text for app/ui/templates/website.html and about.html,
keyed by language.

Not hotel-specific content — that's HotelWebPage's display_name/tagline/
page_title (app/models/hotel_web_page.py). UI_STRINGS is the shared UI copy
around website.html: the input placeholder, accessibility label, send
button, error messages, footer links, logo alt-text prefix, and the About
button's own label. Consumed by _render_website_page() in
app/ui/routes.py. NAHARIYA_STRINGS is the fixed nahariya page's own
bilingual brand name/tagline, consumed by nahariya_chatbot_page().
ABOUT_STRINGS is the /about page's own content, consumed by
_render_about_page() in the same file.
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

# Brand name/title/tagline for app/ui/routes.py::nahariya_chatbot_page(),
# keyed by language — the only hardcoded-but-bilingual page's content
# (nahariya is a fixed tenant, not DB-driven, but still supports
# ?lang=he/en like the generic hotel pages).
NAHARIYA_STRINGS: dict[str, dict[str, str]] = {
    "he": {
        "page_title": "חלון לצפון - מדריך נהרייני מקומי",
        "site_name": "חלון לצפון",
        "tagline": (
            "מדריך נהרייני מקומי — שאלו אותי כל דבר על ביקור בנהריה: "
            "חופים, מסעדות, טיולים ועוד"
        ),
    },
    "en": {
        "page_title": "Window to the North - Local Nahariya Guide",
        "site_name": "Window to the North",
        "tagline": (
            "Local Nahariya guide — ask me anything about visiting "
            "Nahariya: beaches, restaurants, trips and more"
        ),
    },
}

# Content for app/ui/templates/about.html, keyed by language.
ABOUT_STRINGS: dict[str, dict[str, str]] = {
    "he": {
        "page_title": "אודות",
        "heading": "אליעד עיני",
        "photo_alt": "אליעד עיני",
        "bio_html": (
            "<h2>אודות פרויקט הבוט</h2>"
            "<p>חלון לצפון "
            "הוא פרויקט בוט "
            "שנבנה כדי לעזור "
            "למבקרים, לתושבים "
            "חדשים ואפילו "
            "לתושבים מקומיים "
            "לנהל וליהנות מהזמן "
            "שלהם בצפון.</p>"
            "<p>הוא נבנה כדי לעזור "
            "להרים את התיירות "
            "והעסקים בצפון "
            "אחרי תקופה ארוכה "
            "של מלחמה.</p>"
            "<p>הבוט מבוסס על "
            "מידע שנמסר על ידי "
            "תושבים מקומיים, "
            "בנוסף למידע הרגיל "
            "שכל סוכן AI יכול "
            "למצוא ברשת. אתם "
            "מוזמנים להשתמש "
            "בכפתורים בצ'אט כדי "
            "להציע מידע חדש או "
            "לדרג את המידע הקיים. "
            "הבוט גם יודיע לכם "
            "אם התשובה שלו מבוססת "
            "על מידע מקומי או "
            "מידע כללי מהרשת.</p>"
            "<p>בשלב זה, הבוט מכיר "
            "רק את אזור נהריה "
            "והעיר עצמה. המידע "
            "והקלט של המשתמשים "
            "יכולים להרחיב את "
            "הידע שלו.</p>"
            "<p>חלון לצפון יכול "
            "לשמש בתי מלון לעזור "
            "לאורחים שלהם, ובעתיד "
            "יוכל לתקשר גם דרך "
            "וואטסאפ. הפרויקט הזה "
            "יכול להתרחב לתחומים, "
            "מטרות וסוגי מידע "
            "נוספים רבים.</p>"
            "<h2>קצת עלי</h2>"
            "<p>אני אליעד עיני, "
            "מנהריה, מהנדס תוכנה "
            "בכיר עם יותר מ-12 שנות "
            "ניסיון בפיתוח תוכנה "
            "בחברות שונות.</p>"
            "<p>נשוי לנעם, אבא "
            "ל-3 ילדים מתוקים.</p>"
            "<p>מוזמנים לפנות אליי "
            "בשאלות והצעות לגבי "
            "הבוט לכתובת: "
            '<a href="mailto:eeini1983@gmail.com">eeini1983@gmail.com</a></p>'
        ),
        "back_link_text": "חזרה לאתר",
    },
    "en": {
        "page_title": "About",
        "heading": "Eliad Eini",
        "photo_alt": "Eliad Eini",
        "bio_html": (
            "<h2>About the Bot Project</h2>"
            "<p>Window to the North is a bot project that was built to help "
            "visitors, new residents, or even locals manage and enjoy their "
            "time in the north.</p>"
            "<p>It was built in order to elevate tourism and businesses in "
            "the north after a long time of war.</p>"
            "<p>The bot is based on data given by locals, in addition to the "
            "regular data that any AI agent can find on the web. Feel free "
            "to use the buttons in the chat to suggest new data or rate the "
            "existing data. The bot will also tell you whether its answer "
            "used local data or general data from the web.</p>"
            "<p>For the time being, the bot only knows Nahariya's region "
            "and the city itself. Users' data and input can extend its "
            "knowledge.</p>"
            "<p>Window to the North can be used by hotels to help their "
            "guests, and will be able to communicate through WhatsApp in "
            "the future. This project can be extended to many other "
            "fields, purposes, and other types of data.</p>"
            "<h2>About Me</h2>"
            "<p>I'm Eliad Eini, from Nahariya, a Senior Software Engineer "
            "with more than 12 years of software development experience in "
            "various companies.</p>"
            "<p>Married to Noam, father to 3 sweet kids.</p>"
            "<p>You are welcome to contact me with questions and "
            "suggestions about the bot at "
            '<a href="mailto:eeini1983@gmail.com">eeini1983@gmail.com</a>.</p>'
        ),
        "back_link_text": "Back to site",
    },
}
