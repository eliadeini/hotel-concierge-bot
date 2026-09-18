# `app/ui/` — browser front ends (hotel demo + public website)

## Why this exists
WhatsApp Business display-name approval has been persistently stuck on Meta's side (see the project's WhatsApp-integration notes), but the bot's actual answering logic works today. These pages let the bot be used in a browser — either demoed to a prospective hotel client, or used as a real public site — with **zero dependency on Meta/Twilio being configured or working**. Both pages call the exact same `gather_context()` (`app/messaging/inbound.py`) and `answer_question()` (`app/api/chat.py`) functions the real WhatsApp path uses, so neither is a separate/divergent implementation — whatever they show is what a real WhatsApp message would get.

There are now two front ends, both backed by the same `POST /demo/ask` endpoint and the same `DEMO_HOTEL_ID` tenant today:
- **`GET /demo`** (`templates/demo.html`) — the WhatsApp-lookalike look, for demoing to hotel clients. Always reachable at this fixed path.
- **`GET /chatbot/nahariya`** (`templates/website.html`) — the general public site look ("נהרייני"), a plain reskin (no WhatsApp chrome) of the same chat mechanics. Path is location-scoped (`/chatbot/<location>`) so other locations can get their own page later without reshuffling this one's URL.
- **`GET /`** redirects to one or the other based on `settings.ui_mode` (`UIMode.website` → `/chatbot/nahariya`, `UIMode.hotel` → `/demo`; see `app/config.py`) — it only picks the default front door, both pages stay directly reachable either way.

## Layout
- **`routes.py`** — `demo_page()`/`nahariya_chatbot_page()` each serve a cached `HTMLResponse` (read from their template once at import time); `index_page()` is the `settings.ui_mode`-driven redirect. `POST /demo/ask` takes `{"question": str}` and returns `{"text": str, "found_in_kb": bool}` (reuses `app.api.chat.ChatResponse` directly, so the "never leak `raw_provider_response`" guarantee can't drift). `DEMO_HOTEL_ID` is hardcoded to `"hotel-demo"`, the only hotel currently seeded in the local dev DB — both pages hit this same tenant for now.
- **`templates/demo.html`** / **`templates/website.html`** — same structure (header/bubbles/input bar), different chrome: WhatsApp green/bubble styling vs. a neutral site palette, and different header copy. Plain HTML/CSS/vanilla JS deliberately in both — no framework, no CDN scripts, no build step, matching the fact that this repo has zero JS tooling anywhere else. Both `fetch()` call `/demo/ask` directly; a `found_in_kb` caption renders under each bot bubble (a deliberate departure from real WhatsApp visuals — it's the actual teaching aid these pages exist to provide, since real WhatsApp can't show it). `website.html`'s caption copy avoids "the hotel" framing, since it isn't tied to one.

## What this deliberately does NOT do
- No `GuestSession`/scripted-onboarding-flow routing (`app/messaging/flow.py`) — every message goes straight to the AI-engine path. There's no "guest checked in via WhatsApp" concept for a browser page.
- No multi-hotel/multi-location selection yet — both pages hit the same hardcoded `DEMO_HOTEL_ID`/knowledge scope. Matches the real bot's behavior otherwise exactly (same system prompt, same structured-output engines, same `ConversationLog` writes).
- No multi-turn memory — neither endpoint nor the real WhatsApp path passes prior conversation turns into `engine.ask()` today, so neither page invents memory the real bot doesn't have.
- No auth beyond "runs locally" — not intended to be exposed publicly as-is.

## Extending it
- **Other locations**: add a new `GET /chatbot/<location>` route + template, following `nahariya_chatbot_page()`'s pattern; wire it to its own tenant once multi-location backend support exists (currently everything points at `DEMO_HOTEL_ID`).
- **Different/multiple hotels**: replace the hardcoded `DEMO_HOTEL_ID` with a request parameter (e.g. `?hotel_id=`) once this needs to serve more than one hotel.
- **Styling/behavior changes**: everything lives in each template's inline `<style>`/`<script>` — no separate asset pipeline to touch.
- **New provider parity**: if `app/messaging/inbound.py`'s real-WhatsApp sequence changes (e.g. a new step is added before the AI-engine call), mirror it in both templates — the whole point of these pages is staying a faithful reflection of that path, not a fork of it.