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
            "<h2>אודות פרויקט חלון לצפון</h2>"
            "<p>חלון לצפון "
            "הוא פרויקט בוט "
            "שנבנה כדי לעזור "
            "למבקרים, תושבים "
            "חדשים ואפילו "
            "לתושבים מקומיים "
            "להתנהל, להסתדר וליהנות מהזמן "
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
            "Watsapp. הפרויקט "
            "יכול להתרחב לתחומים, "
            "מטרות וסוגי מידע "
            "נוספים רבים.</p>"
            "<h2>קצת עלי</h2>"
            "<p>אני אליעד עיני, "
            "מנהריה, מהנדס תוכנה "
            "בכיר עם יותר מ-12 שנות "
            "ניסיון בפיתוח תוכנה "
            "בחברות שונות.</p>"
            "<p>נשוי לנעם ואבא "
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
        "heading": "About Window to the North",
        "photo_alt": "Eliad Eini",
        "bio_html": (
            "<p>Window to the North is a bot project designed to help "
            "visitors, new residents, and locals explore northern Israel "
            "and make the most of their time in the region.</p>"
            "<p>The project was created to support tourism and local "
            "businesses in northern Israel following a prolonged period of "
            "war.</p>"
            "<p>The bot draws on information contributed by locals, "
            "alongside publicly available information from the web. "
            "You're welcome to use the buttons in the chat to suggest new "
            "information or rate existing information. The bot also "
            "indicates whether its answers are based on local "
            "contributions or general information from the web.</p>"
            "<p>Currently, the bot is familiar only with Nahariya and the "
            "surrounding area. User contributions and feedback can help "
            "expand its knowledge.</p>"
            "<p>Window to the North can also be used by hotels to assist "
            "their guests, with plans to introduce WhatsApp integration in "
            "the future. The project could eventually be expanded to cover "
            "additional regions, use cases, and types of information.</p>"
            "<h2>About Me</h2>"
            "<p>I'm Eliad Eini, a senior software engineer from Nahariya, "
            "with over 12 years of professional software development "
            "experience.</p>"
            "<p>I'm married to Noam, and we have three wonderful "
            "children.</p>"
            "<p>Feel free to contact me with any questions or suggestions "
            "about the bot at "
            '<a href="mailto:eeini1983@gmail.com">eeini1983@gmail.com</a>.</p>'
        ),
        "back_link_text": "Back to site",
    },
}
