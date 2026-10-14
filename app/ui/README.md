# `app/ui/` — browser front ends (hotel demo + public website + per-hotel pages)

## Why this exists
WhatsApp Business display-name approval has been persistently stuck on Meta's side (see the project's WhatsApp-integration notes), but the bot's actual answering logic works today. These pages let the bot be used in a browser — either demoed to a prospective hotel client, or used as a real public site — with **zero dependency on Meta/Twilio being configured or working**. Every page calls the exact same `gather_context()` (`app/messaging/inbound.py`) and `answer_question()` (`app/api/chat.py`) functions the real WhatsApp path uses, so none of them are a separate/divergent implementation — whatever they show is what a real WhatsApp message would get.

There are two fixed front ends, plus a generic, DB-configured one any hotel
can get (each backed by its own tenant, so shared knowledge content can be
neutralized for the public site without affecting the hotel demo — see
`app/messaging/inbound.py::gather_context`):
- **`GET /demo`** (`templates/demo.html`, `POST /demo/ask`) — the WhatsApp-lookalike look, for demoing to hotel clients, backed by `DEMO_HOTEL_ID` (`"hotel-demo"`). Always reachable at this fixed path.
- **`GET /chatbot/nahariya`** (`templates/website.html`, `POST /chatbot/nahariya/ask`) — the general public site look ("נהרייני"), a plain reskin (no WhatsApp chrome) of the same chat mechanics, backed by its own separate tenant `NAHARIYA_GUIDE_HOTEL_ID` (`"nahariya-guide"`). Hardcoded on purpose — the first, fixed public site — not DB-driven like the generic pages below.
- **`GET /chatbot/{location}/{slug}`** (`POST /chatbot/{location}/{slug}/ask`) — a **generic**, per-hotel branded page: any hotel in `hotel_settings` can get one, fully configured from data (see "Generic hotel pages" below), no code change needed per hotel. Supports `?lang=he`/`?lang=en` (see below); any other value, or no param at all, falls back to English.
- **`GET /`** redirects to the demo or the fixed nahariya page based on `settings.ui_mode` (`UIMode.website` → `/chatbot/nahariya`, `UIMode.hotel` → `/demo`; see `app/config.py`) — it only picks the default front door; every page above stays directly reachable either way.

## Layout
- **`routes.py`** — `demo_page()`/`nahariya_chatbot_page()`/`hotel_web_page()` each serve HTML; `index_page()` is the `settings.ui_mode`-driven redirect. `demo.html` is served as-is (cached raw string, read once at import). `website.html` is instead a **template** with `__TOKEN__` placeholders (`_WEBSITE_TEMPLATE`, also read once at import) — `_render_website_page(...)` fills it via plain `str.replace()` calls (not `str.format()`, since the CSS is full of literal `{}`). Both `nahariya_chatbot_page()` (hardcoded literal values) and `hotel_web_page()` (DB-sourced, `html.escape()`'d — see below) call the same renderer, so there's exactly one template to keep in sync, not two. The shared `_ask()` helper returns `{"text": str, "found_in_kb": bool, "conversation_id": int}` (reuses `app.api.chat.ChatResponse` directly, so the "never leak `raw_provider_response`" guarantee can't drift). `POST /notes` (shared by every page, not tenant-scoped — `conversation_id` already identifies the hotel) accepts a guest's like/dislike and/or free-text note against a specific `conversation_id` — see "Guest notes" below.
- **`templates/demo.html`** / **`templates/website.html`** — same structure (header/bubbles/input bar), different chrome: WhatsApp green/bubble styling vs. a neutral site palette, and different header copy. Plain HTML/CSS/vanilla JS deliberately in both — no framework, no CDN scripts, no build step, matching the fact that this repo has zero JS tooling anywhere else. Both `fetch()` their respective `/ask` endpoint; a `found_in_kb` caption and a 👍/👎/"leave a note" row render under each bot bubble (a deliberate departure from real WhatsApp visuals — it's the actual teaching aid these pages exist to provide, since real WhatsApp can't show either). `website.html`'s caption copy avoids "the hotel" framing, since it isn't tied to one.

## Generic hotel pages
Any hotel can get its own branded page at `/chatbot/{location}/{slug}` —
**no hotel-specific name/text/image is ever committed to this public
repo**; everything comes from a `HotelWebPage` row (`app/models/hotel_web_page.py`,
one-to-one with `HotelSettings`) plus gitignored image files.

**End-to-end, using made-up example data** (never real hotel data in
docs/commits — substitute your actual values when you run this for real):

1. Register the hotel and its page together — `web_page` is optional on
   `POST /admin/hotels`, so one call creates both. `display_name`/
   `tagline`/`page_title` are each an object keyed by language
   (`"he"`/`"en"`) rather than a plain string — `"he"` is required on
   every one of the three, `"en"` is optional per field (missing it just
   means `?lang=en` falls back to the Hebrew text for that field):
   ```bash
   curl -X POST http://127.0.0.1:8000/admin/hotels \
     -H "Content-Type: application/json" \
     -H "X-Admin-Token: <ADMIN_TOKEN>" \
     -d '{
       "hotel_id": "hotel-example",
       "ai_engine": "openai",
       "api_key": "sk-...",
       "web_page": {
         "location": "beachtown",
         "slug": "demo",
         "display_name": {"he": "מלון לדוגמה", "en": "Example Hotel"},
         "tagline": {"he": "שאלו אותי כל דבר על הביקור", "en": "Ask me anything about your stay"},
         "page_title": {"he": "מלון לדוגמה — הקונסיירז הדיגיטלי", "en": "Example Hotel — Digital Concierge"},
         "logo_file": "logo.png",
         "background_file": "background.jpg"
       }
     }'
   ```
   `location`/`slug` must be lowercase `a-z0-9-` (they form the URL);
   `logo_file`/`background_file` must be plain file names, no path. 404 for
   an unknown `hotel_id`, 409 if another hotel already owns that
   `location`+`slug`, 422 for invalid input — including a missing `"he"`
   key or an unsupported language key (only `SUPPORTED_LANGUAGES` from
   `app/models/hotel_web_page.py`, currently `{"he", "en"}`) on any of the
   three fields. To edit branding later without resupplying `api_key`, use
   `PUT /admin/hotels/{hotel_id}/web-page` with the same
   `location`/`slug`/`display_name`/`tagline`/`page_title`/
   `logo_file`/`background_file`/`enabled` fields directly (not nested).
2. Drop the actual image files locally at
   `app/ui/hotel_assets/hotel-example/logo.png` and `.../background.jpg`
   (see that folder's `README.md` — everything in there is gitignored by
   convention, nothing to commit).
3. Push them to the server: `deploy/sync-private-data.sh` (now also syncs
   `app/ui/hotel_assets/`, binary-safe — see that script's own comments).
4. Visit `/chatbot/beachtown/demo` (English, the default) or
   `/chatbot/beachtown/demo?lang=he` (Hebrew). Set `enabled: false` (same
   PUT endpoint) to take a page down without deleting its data.

**Language switching**: the generic page's `<html lang="...">`, the
hotel's own `display_name`/`tagline`/`page_title`, and all of the
template's shared chrome text (input placeholder, send button,
accessibility label, error messages, footer links — `UI_STRINGS` in
`app/ui/strings.py`) follow `?lang=he`/`?lang=en` — any other value, or
no param, falls back to English (`DEFAULT_LANGUAGE`). There's no
RTL/LTR-specific CSS in this template to flip either way — both
languages render in the same layout. The fixed `/demo` and
`/chatbot/nahariya` pages don't take this param at all — they're
hardcoded to Hebrew exactly as before.

A hotel with `is_test=True` (`HotelSettings.is_test`) never gets served
here — same 404 as a missing or disabled page, so a prober can't tell
those three cases apart from the outside.

## Guest notes
Each bot reply gets a 👍/👎 pair (fires immediately, no text required) and a
"leave a note" link (opens an inline textarea) — see `appendNoteActions()`/
`openNoteBox()` in either template's `<script>`. Both post to `POST /notes`
with the `conversation_id` from that reply's `/ask` response, handled by
`app/user_notes.py::submit_user_note()`. No guest auth — same trust level as
the chat endpoints themselves. Review them via `GET /admin/notes` (see root
`README.md`'s "Guest notes" section and `app/models/README.md`'s
`user_note.py` entry) — there's no self-service editing yet, you apply any
resulting content change yourself.

## What this deliberately does NOT do
- No `GuestSession`/scripted-onboarding-flow routing (`app/messaging/flow.py`) — every message goes straight to the AI-engine path. There's no "guest checked in via WhatsApp" concept for a browser page.
- `/demo` and `/chatbot/nahariya` still hit their own hardcoded tenant constants (`DEMO_HOTEL_ID`, `NAHARIYA_GUIDE_HOTEL_ID`) on purpose — they're the fixed/original front ends, not meant to become DB-driven. Generic, data-driven hotels use `/chatbot/{location}/{slug}` instead (see above), not a `?hotel_id=`-style query param on these fixed paths.
- No multi-turn memory — neither endpoint nor the real WhatsApp path passes prior conversation turns into `engine.ask()` today, so no page invents memory the real bot doesn't have.
- No auth beyond "runs locally" on any of these pages — not intended to be exposed publicly as-is. The `/notes` endpoint matches this same trust level. (The admin endpoints that configure `HotelWebPage` rows *are* token-protected — see `app/api/chat.py`.)

## Extending it
- **New generic hotel page**: no code change needed — see "Generic hotel pages" above.
- **Styling/behavior changes**: everything lives in each template's inline `<style>`/`<script>` — no separate asset pipeline to touch. A change to `website.html` affects nahariya and every generic hotel page at once (one shared template); a change to `demo.html` affects only `/demo`.
- **New provider parity**: if `app/messaging/inbound.py`'s real-WhatsApp sequence changes (e.g. a new step is added before the AI-engine call), mirror it in both templates — the whole point of these pages is staying a faithful reflection of that path, not a fork of it.