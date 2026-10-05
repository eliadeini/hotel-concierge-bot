# `app/ui/` — browser front ends (hotel demo + public website)

## Why this exists
WhatsApp Business display-name approval has been persistently stuck on Meta's side (see the project's WhatsApp-integration notes), but the bot's actual answering logic works today. These pages let the bot be used in a browser — either demoed to a prospective hotel client, or used as a real public site — with **zero dependency on Meta/Twilio being configured or working**. Both pages call the exact same `gather_context()` (`app/messaging/inbound.py`) and `answer_question()` (`app/api/chat.py`) functions the real WhatsApp path uses, so neither is a separate/divergent implementation — whatever they show is what a real WhatsApp message would get.

There are now two front ends, each backed by its own tenant (so shared
knowledge content can be neutralized for the public site without affecting
the hotel demo — see `app/messaging/inbound.py::gather_context`):
- **`GET /demo`** (`templates/demo.html`, `POST /demo/ask`) — the WhatsApp-lookalike look, for demoing to hotel clients, backed by `DEMO_HOTEL_ID` (`"hotel-demo"`). Always reachable at this fixed path.
- **`GET /chatbot/nahariya`** (`templates/website.html`, `POST /chatbot/nahariya/ask`) — the general public site look ("נהרייני"), a plain reskin (no WhatsApp chrome) of the same chat mechanics, backed by its own separate tenant `NAHARIYA_GUIDE_HOTEL_ID` (`"nahariya-guide"`). Path is location-scoped (`/chatbot/<location>`) so other locations can get their own page later without reshuffling this one's URL.
- **`GET /`** redirects to one or the other based on `settings.ui_mode` (`UIMode.website` → `/chatbot/nahariya`, `UIMode.hotel` → `/demo`; see `app/config.py`) — it only picks the default front door, both pages stay directly reachable either way.

## Layout
- **`routes.py`** — `demo_page()`/`nahariya_chatbot_page()` each serve a cached `HTMLResponse` (read from their template once at import time); `index_page()` is the `settings.ui_mode`-driven redirect. The shared `_ask()` helper returns `{"text": str, "found_in_kb": bool, "conversation_id": int}` (reuses `app.api.chat.ChatResponse` directly, so the "never leak `raw_provider_response`" guarantee can't drift). `POST /notes` (shared by both pages, not tenant-scoped — `conversation_id` already identifies the hotel) accepts a guest's like/dislike and/or free-text note against a specific `conversation_id` — see "Guest notes" below.
- **`templates/demo.html`** / **`templates/website.html`** — same structure (header/bubbles/input bar), different chrome: WhatsApp green/bubble styling vs. a neutral site palette, and different header copy. Plain HTML/CSS/vanilla JS deliberately in both — no framework, no CDN scripts, no build step, matching the fact that this repo has zero JS tooling anywhere else. Both `fetch()` their respective `/ask` endpoint; a `found_in_kb` caption and a 👍/👎/"leave a note" row render under each bot bubble (a deliberate departure from real WhatsApp visuals — it's the actual teaching aid these pages exist to provide, since real WhatsApp can't show either). `website.html`'s caption copy avoids "the hotel" framing, since it isn't tied to one.

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
- No generic multi-hotel/multi-location selection yet — each page hits its own hardcoded tenant constant (`DEMO_HOTEL_ID`, `NAHARIYA_GUIDE_HOTEL_ID`), not a request-driven `?hotel_id=`. Matches the real bot's behavior otherwise exactly (same system prompt, same structured-output engines, same `ConversationLog` writes).
- No multi-turn memory — neither endpoint nor the real WhatsApp path passes prior conversation turns into `engine.ask()` today, so neither page invents memory the real bot doesn't have.
- No auth beyond "runs locally" — not intended to be exposed publicly as-is. The new `/notes` endpoint matches this same trust level.

## Extending it
- **Other locations**: add a new `GET /chatbot/<location>` route + template, following `nahariya_chatbot_page()`'s pattern, and give it its own tenant constant (following `NAHARIYA_GUIDE_HOTEL_ID`'s pattern) — there's no generic `?hotel_id=` selector yet, so each new front end hardcodes its own tenant for now.
- **Different/multiple hotels**: replace the hardcoded per-page tenant constants with a request parameter (e.g. `?hotel_id=`) once this needs a generic selector instead of one hardcoded tenant per front end.
- **Styling/behavior changes**: everything lives in each template's inline `<style>`/`<script>` — no separate asset pipeline to touch.
- **New provider parity**: if `app/messaging/inbound.py`'s real-WhatsApp sequence changes (e.g. a new step is added before the AI-engine call), mirror it in both templates — the whole point of these pages is staying a faithful reflection of that path, not a fork of it.