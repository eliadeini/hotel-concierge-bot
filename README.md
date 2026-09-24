# Hotel Concierge Bot — Phase 1

A concierge chat bot for a hotel: answers guest questions by combining LLM
general knowledge with local Markdown "skills" files, returns a structured
`found_in_kb` flag, and logs conversations anonymously. Runs as a WhatsApp
bot from phase 1. Providers (OpenAI / Claude), knowledge storage, and
WhatsApp messaging (Twilio / Meta) each sit behind an abstraction layer, so
all three are swappable via configuration.

Planning docs: `hotel_concierge_bot_plan.md` (strategy) and
`claude_code_brief_phase1.md` (implementation brief).

## Setup

```powershell
# from the project root
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

# create your .env
copy .env.example .env
.venv\Scripts\python scripts\generate_master_key.py   # paste into MASTER_ENCRYPTION_KEY
# also set ADMIN_TOKEN to any long random string
```

For local dev without a real Twilio/Meta account, leave `MESSAGING_PROVIDER=mock`
in `.env` (the default) — outbound WhatsApp sends are logged instead of sent.
Switch it to `twilio` and fill in the `TWILIO_*` vars once you have a real
account (see `app/messaging/README.md`).

## Getting API keys

A ChatGPT Plus/Pro or Claude Pro subscription does **not** include API access —
the API is billed separately (pay-as-you-go; ~$5 of credit is plenty for
phase 1 testing):

- **OpenAI**: <https://platform.openai.com> → sign in → *Settings → Billing* →
  add credit ($5 minimum) → *API Keys* → *Create new secret key*.
- **Anthropic (Claude)**: <https://console.anthropic.com> → sign in →
  *Billing* → add credit → *API Keys* → *Create Key*.

Keys are stored **encrypted** in the local database via the admin endpoint —
never committed, never logged.

## Run

```powershell
.venv\Scripts\python -m uvicorn app.main:app --reload
```

Register a hotel (repeat with `"ai_engine": "claude"` + an Anthropic key to
test the engine swap):

```powershell
curl -X POST http://127.0.0.1:8000/admin/hotels `
  -H "Content-Type: application/json" `
  -H "X-Admin-Token: <your ADMIN_TOKEN>" `
  -d '{"hotel_id": "hotel-test-prague", "ai_engine": "openai", "api_key": "sk-...", "is_test": true}'
```

Chat:

```powershell
curl -X POST http://127.0.0.1:8000/chat `
  -H "Content-Type: application/json" `
  -d '{"hotel_id": "hotel-test-prague", "region": "prague", "question": "What is the most famous dish at U Fleku?"}'
```

## Manual test plan (found_in_kb proof)

The `prague` region contains a **fictional** fact — the "Golden Vltava
Dumplings" at U Fleků — that cannot come from general knowledge:

1. Ask about U Fleků's famous dish → answer mentions the fictional dumplings,
   `found_in_kb: true`.
2. Ask about prague nightlife (no skill content) → sensible general answer,
   `found_in_kb: false`.
3. Flip the hotel's `ai_engine` to `claude` via `/admin/hotels` → repeat both;
   behavior equivalent with no code change.
4. Ask in Hebrew and in English → answered in the guest's language, Hebrew
   business names preserved alongside translations.

## Tests

```powershell
.venv\Scripts\python -m pytest
```

Unit tests use fake engines and fake knowledge sources — no API keys, no disk,
no network.

## Structure

- `app/engines/` — `AIEngine` interface + OpenAI/Claude adapters + factory
  (engine chosen per hotel via the `hotel_settings` table)
- `app/knowledge/` — `KnowledgeSource` interface + Markdown implementation +
  region skill files (`files/{region}/*.md`, YAML frontmatter entries)
- `app/messaging/` — `MessagingProvider` interface + Twilio/Meta adapters +
  rate-limited factory (WhatsApp provider chosen per hotel, with global
  fallback; see `app/messaging/README.md`)
- `app/api/chat.py` — `POST /chat`, `POST /admin/hotels`, and
  `POST /admin/hotels/{hotel_id}/guests` (registers a guest's stay and
  triggers the scripted WhatsApp onboarding flow — see
  `app/messaging/README.md`)
- `app/api/meta_whatsapp_webhook.py` — `GET`/`POST /webhook/whatsapp`
  (inbound WhatsApp messages via Meta Cloud API; see `app/messaging/README.md`)
- `app/api/twilio_whatsapp_webhook.py` — `POST /webhook/whatsapp/twilio`
  (same, via Twilio; not currently live-configured)
- `app/models/` — `hotel_settings` (encrypted API keys), `conversation_log`
  (anonymous), plus `hotel_contact`, `hotel_region_tag`,
  `hotel_messaging_settings`, `message_rate_limit_counter`,
  `guest_session` (see `app/models/README.md`)
- `app/security/crypto.py` — Fernet encryption; master key from env only

## Deployment

Targets an Ubuntu EC2 instance behind Apache, with HTTPS via Certbot and
deploys via GitHub Actions. See `deploy/` for the actual config.

**Bootstrap a new server** (clone the repo to `/home/ubuntu/hotel-concierge-bot`
first, then create `.env` there from `.env.example` with real values):

```bash
git clone <this-repo-url> /home/ubuntu/hotel-concierge-bot
cd /home/ubuntu/hotel-concierge-bot
cp .env.example .env   # fill in real values — never commit this file
./deploy/setup.sh <domain> <email>
```

This installs system packages, creates a venv, installs the `concierge`
systemd service (runs `uvicorn` on `127.0.0.1:8000`), and configures Apache
as a reverse proxy. It's safe to re-run.

**Issue the HTTPS certificate** once DNS for your domain points at the
server (the command above prints this at the end too):

```bash
sudo certbot --apache -d <domain> -m <email> --agree-tos --redirect
```

**Set up GitHub Actions deploys** (push to `main` → SSH in, `git pull`,
reinstall deps, restart the service): add these repo secrets under
*Settings → Secrets and variables → Actions*:

- `EC2_HOST` — the server's public IP or domain
- `EC2_USER` — `ubuntu`
- `EC2_SSH_KEY` — the private key matching a public key in the server's
  `~/.ssh/authorized_keys`

## Local-only data (not in this repo)

Two knowledge files belong to a real hotel this bot was piloted with, and
are intentionally excluded from git (see `.gitignore`) so no real business's
name or address ends up in a public repo. To run the bot against your own
hotel, create your own copies at the same paths — both have a tracked
fictional example showing the exact format to follow.

### `app/knowledge/hotel_skills/<your-hotel-id>.md`
**Purpose:** the hotel's WhatsApp onboarding greeting plus tone/branding
instructions, appended to the AI system prompt for every chat with that
hotel's guests. Pointed to per-hotel by `HotelSettings.hotel_skill_path`.

**Format:** plain text, freely mixing the greeting and the tone
instructions — see the tracked example at
[`app/knowledge/hotel_skills/example.md`](app/knowledge/hotel_skills/example.md):
```
ברוך הבא למלון הדוגמה. אנו שמחים לארח אותך. אני הצ'אט בוט של המלון,
אלווה אותך ואעזור לך לתכנן את החופשה ואת הביקור. אתה מוזמן להתייעץ איתי
לגבי הביקור.

טון: קליל והומוריסטי במידה, אבל תמיד מכבד ומועיל. אפשר להשתמש בהומור עדין
כשזה מתאים, אבל לא על חשבון דיוק המידע.
```

### `app/knowledge/files/<region>/<category>.md`
**Purpose:** regional knowledge-base entries (restaurants, attractions,
etc.) that `MarkdownFileSource.get_context(hotel_id, region, category)`
loads as context for that region's questions — this is the data that lets
`found_in_kb` be `true`.

**Format:** one or more YAML-frontmatter entries per file, each followed by
free-text body — see the tracked example at
[`app/knowledge/files/example-region/restaurants.md`](app/knowledge/files/example-region/restaurants.md):
```markdown
---
region: example-region
category: restaurants
name: Fictional Sushi Bar
tags: [סושי, קרוב למלון]
updated: 2026-08-01
---
כ-5 דקות הליכה ממלון הדוגמה. מומלץ לארוחה יושבת, לא רק למשלוחים.
```
