# `app/ui/` — WhatsApp-lookalike browser demo

## Why this exists
WhatsApp Business display-name approval has been persistently stuck on Meta's side (see the project's WhatsApp-integration notes), but the bot's actual answering logic works today. This page lets the bot be demoed in a browser — to the hotel owner, or anyone else — with **zero dependency on Meta/Twilio being configured or working**. It calls the exact same `gather_context()` (`app/messaging/inbound.py`) and `answer_question()` (`app/api/chat.py`) functions the real WhatsApp path uses, so this is provably not a separate/divergent implementation — whatever it shows is what a real WhatsApp message would get.

This is not meant to stay a throwaway demo. The intent is for it to grow into the real future channel — a website chat widget alongside WhatsApp (this was floated as a possible future channel in `hotel_concierge_bot_plan.md`). The one deliberate v1 simplification, a hardcoded demo hotel, is the first thing to generalize when that happens — not a sign this needs rewriting from scratch.

## Layout
- **`routes.py`** — `GET /demo` serves the page (a cached `HTMLResponse`, read from `templates/demo.html` once at import time); `POST /demo/ask` takes `{"question": str}` and returns `{"text": str, "found_in_kb": bool}` (reuses `app.api.chat.ChatResponse` directly, so the "never leak `raw_provider_response`" guarantee can't drift between the two endpoints). `DEMO_HOTEL_ID` is hardcoded to `"hotel-demo"`, the only hotel currently seeded in the local dev DB.
- **`templates/demo.html`** — the entire page: WhatsApp-style header/bubbles/input bar, with inline `<style>` and `<script>`. Plain HTML/CSS/vanilla JS deliberately — no framework, no CDN scripts, no build step, matching the fact that this repo has zero JS tooling anywhere else. `fetch()` calls `/demo/ask` directly; a `found_in_kb` caption is rendered under each bot bubble (a deliberate departure from real WhatsApp visuals — it's the actual teaching aid this page exists to provide, since real WhatsApp can't show it).

## What this deliberately does NOT do
- No `GuestSession`/scripted-onboarding-flow routing (`app/messaging/flow.py`) — every message goes straight to the AI-engine path. There's no "guest checked in via WhatsApp" concept for a browser page.
- No multi-hotel selection — hardcoded to `DEMO_HOTEL_ID`. Matches the real bot's behavior otherwise exactly (same system prompt, same structured-output engines, same `ConversationLog` writes).
- No multi-turn memory — neither this endpoint nor the real WhatsApp path passes prior conversation turns into `engine.ask()` today, so the demo correctly doesn't invent memory the real bot doesn't have.
- No auth beyond "runs locally" — not intended to be exposed publicly as-is.

## Extending it
- **Different/multiple hotels**: replace the hardcoded `DEMO_HOTEL_ID` with a request parameter (e.g. `?hotel_id=`) once this needs to serve more than one hotel.
- **Styling/behavior changes**: everything lives in `templates/demo.html`'s inline `<style>`/`<script>` — no separate asset pipeline to touch.
- **New provider parity**: if `app/messaging/inbound.py`'s real-WhatsApp sequence changes (e.g. a new step is added before the AI-engine call), mirror it here too — the whole point of this page is staying a faithful reflection of that path, not a fork of it.