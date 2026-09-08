# Hotel Concierge Bot — API Testing Prompt (Postman, real GPT)

*Hand this whole document to Co-Work as-is. It explains how to set up Postman and lists 5 tests per endpoint, using real OpenAI (ChatGPT) answers — no mocks.*

---

## 0. Before you start

- Python environment set up per the project README (`.venv` created, `pip install -r requirements.txt` run).
- `.env` configured with `MASTER_ENCRYPTION_KEY`, `ADMIN_TOKEN`, `DATABASE_URL`.
- A **real OpenAI API key** with billing enabled (a ChatGPT Plus/Pro subscription does not include API access — this is billed separately, ~$5 of credit is plenty). Get one at <https://platform.openai.com> → *Settings → Billing* → add credit → *API Keys* → *Create new secret key*.
- Postman installed.

### Start the server

From the project root (`C:\Users\eliad\DevProjects\Hotel Concierge Bot`):

```powershell
.venv\Scripts\python -m uvicorn app.main:app --reload
```

The server listens on `http://127.0.0.1:8000`. Confirm it's up: `GET http://127.0.0.1:8000/health` should return `{"status":"ok"}`.

---

## 1. Postman setup

1. Create a new **Collection** named "Hotel Concierge Bot".
2. Create an **Environment** named "local" with these variables:
   - `base_url` = `http://127.0.0.1:8000`
   - `admin_token` = *(the `ADMIN_TOKEN` value from `.env`)*
   - `openai_api_key` = *(your real OpenAI secret key, `sk-...`)*
3. Select the "local" environment (top-right dropdown) before running anything.
4. Every request URL should start with `{{base_url}}`.
5. For all requests below: Body tab → **raw** → **JSON**.
6. Add assertions per request in the **Tests** tab (JavaScript, `pm.test(...)`) — scripts are given below for each test. After clicking **Send**, Postman shows pass/fail for each assertion under the **Test Results** tab of the response.
7. If something fails unexpectedly, open **View → Show Postman Console** to see the exact request/response.

---

## 2. Register a real hotel first (needed before any `/chat` test)

**POST** `{{base_url}}/admin/hotels`
Headers: `X-Admin-Token: {{admin_token}}`
Body (JSON):

```json
{
  "hotel_id": "hotel-test-prague",
  "ai_engine": "openai",
  "api_key": "{{openai_api_key}}",
  "is_test": true
}
```

This uses the built-in `prague` test knowledge region (`app/knowledge/files/prague/restaurants.md`), which contains one **fictional** fact — the "Golden Vltava Dumplings" at U Fleků — that cannot come from OpenAI's general knowledge. If a `/chat` answer mentions it, that's proof the knowledge base (not just general LLM knowledge) drove the answer.

---

## 3. `GET /health` — 5 tests

**1. Basic health check**
`GET {{base_url}}/health`
```js
pm.test("status 200", () => pm.response.to.have.status(200));
pm.test("body is ok", () => pm.expect(pm.response.json()).to.eql({status: "ok"}));
```

**2. Content-Type is JSON**
Same request.
```js
pm.test("json content-type", () => pm.response.to.have.header("Content-Type", "application/json"));
```

**3. Fast response (sanity check, not a load test)**
Same request.
```js
pm.test("responds under 500ms", () => pm.expect(pm.response.responseTime).to.be.below(500));
```

**4. Idempotent — call twice, identical result**
Send the request twice in a row; both should return the same body.
```js
pm.test("still ok", () => pm.expect(pm.response.json().status).to.eql("ok"));
```

**5. Wrong method rejected**
`POST {{base_url}}/health` (no body)
```js
pm.test("405 method not allowed", () => pm.response.to.have.status(405));
```

---

## 4. `POST /admin/hotels` — 5 tests

**1. Create hotel with a real OpenAI key**
As in section 2 above.
```js
pm.test("status 200", () => pm.response.to.have.status(200));
const body = pm.response.json();
pm.test("correct fields echoed", () => {
  pm.expect(body.hotel_id).to.eql("hotel-test-prague");
  pm.expect(body.ai_engine).to.eql("openai");
  pm.expect(body.is_test).to.eql(true);
});
pm.test("api key never echoed back", () => pm.expect(pm.response.text()).to.not.include(pm.environment.get("openai_api_key")));
```

**2. Missing admin token rejected**
Same body, but remove the `X-Admin-Token` header entirely.
```js
pm.test("401 unauthorized", () => pm.response.to.have.status(401));
```

**3. Wrong admin token rejected**
Same body, header `X-Admin-Token: wrong-token`.
```js
pm.test("401 unauthorized", () => pm.response.to.have.status(401));
```

**4. Updating an existing hotel switches its settings**
Re-POST to the same `hotel_id` ("hotel-test-prague") with `"is_test": false`. (Careful — this hides it from the "test region" flag; set it back to `true` afterward before running the `/chat` tests below.)
```js
pm.test("status 200", () => pm.response.to.have.status(200));
pm.test("is_test updated", () => pm.expect(pm.response.json().is_test).to.eql(false));
```

**5. Validation error on missing required field**
Body with `api_key` omitted entirely:
```json
{"hotel_id": "bad-request-test", "ai_engine": "openai", "is_test": true}
```
```js
pm.test("422 validation error", () => pm.response.to.have.status(422));
```

---

## 5. `POST /chat` — 5 tests (real OpenAI answers)

*These calls make real, billed OpenAI requests.* Make sure `hotel-test-prague` is registered with `is_test: true` (section 2) before running these.

**1. Knowledge-base fact is used (found_in_kb: true)**
Body:
```json
{"hotel_id": "hotel-test-prague", "region": "prague", "question": "What is the most famous dish at U Fleku?"}
```
```js
pm.test("status 200", () => pm.response.to.have.status(200));
const body = pm.response.json();
pm.test("found_in_kb is true", () => pm.expect(body.found_in_kb).to.eql(true));
pm.test("mentions the fictional dish", () => pm.expect(body.text.toLowerCase()).to.include("golden vltava dumplings"));
```

**2. No relevant knowledge (found_in_kb: false), still a sensible answer**
Body:
```json
{"hotel_id": "hotel-test-prague", "region": "prague", "question": "What's the best nightlife area in Prague?"}
```
```js
pm.test("status 200", () => pm.response.to.have.status(200));
const body = pm.response.json();
pm.test("found_in_kb is false", () => pm.expect(body.found_in_kb).to.eql(false));
pm.test("answer is non-empty", () => pm.expect(body.text.length).to.be.above(0));
```

**3. Answers in the guest's language (Hebrew in, Hebrew out)**
Body:
```json
{"hotel_id": "hotel-test-prague", "region": "prague", "question": "מה המנה הכי מפורסמת ב-U Fleku?"}
```
```js
pm.test("status 200", () => pm.response.to.have.status(200));
const text = pm.response.json().text;
pm.test("answer contains Hebrew characters", () => pm.expect(/[\u0590-\u05FF]/.test(text)).to.eql(true));
```

**4. Unknown hotel_id rejected**
Body:
```json
{"hotel_id": "no-such-hotel", "region": "prague", "question": "hi"}
```
```js
pm.test("404 unknown hotel", () => pm.response.to.have.status(404));
```

**5. Validation error on empty question**
Body:
```json
{"hotel_id": "hotel-test-prague", "region": "prague", "question": ""}
```
```js
pm.test("422 validation error", () => pm.response.to.have.status(422));
```

---

## 6. WhatsApp mechanism — setup (mock mode)

This tests the *whole* inbound WhatsApp pipeline — signature validation, hotel lookup, a **real** OpenAI-generated reply — without needing a real Twilio account yet. `.env` already has:

```
MESSAGING_PROVIDER=mock
TWILIO_AUTH_TOKEN=local-test-token
TWILIO_WHATSAPP_NUMBER=whatsapp:+15550001111
WHATSAPP_WEBHOOK_VERIFY_TOKEN=my-verify-token
```

`MESSAGING_PROVIDER=mock` only affects the final delivery hop — instead of actually calling Twilio's API, the generated reply is logged to the server console. The OpenAI call that produces the reply text is still 100% real. Restart the server after any `.env` change (`uvicorn --reload` doesn't watch `.env`).

**One-time setup**: unlike `/chat`, the webhook doesn't take a `region` in the request — it resolves knowledge context from the hotel's `HotelRegionTag` list instead (see `_gather_context` in `app/api/whatsapp_webhook.py`). There's no admin endpoint for tags yet, so add one directly, after registering `hotel-test-prague` (section 2):

```powershell
.venv\Scripts\python -c "from app.db import SessionLocal, init_db; from app.models.hotel_settings import HotelSettings; from app.models.hotel_region_tag import HotelRegionTag; init_db(); db = SessionLocal(); hotel = db.query(HotelSettings).filter_by(hotel_id='hotel-test-prague').one(); db.add(HotelRegionTag(hotel_settings_id=hotel.id, tag='prague')); db.commit(); print('tagged')"
```

Add three more Postman environment variables:
- `twilio_auth_token` = `local-test-token`
- `webhook_url` = `{{base_url}}/webhook/whatsapp`
- `twilio_number` = `whatsapp:+15550001111`

The tests below assume `hotel-test-prague` is the **only** hotel row in the database (fresh DB, or you haven't registered other hotels) — that's what lets the single-number fallback resolve unambiguously.

---

## 7. `GET /webhook/whatsapp` — 5 tests (Meta-style verification handshake)

**1. Correct token verified**
`GET {{base_url}}/webhook/whatsapp?hub.mode=subscribe&hub.verify_token=my-verify-token&hub.challenge=echo123`
```js
pm.test("status 200", () => pm.response.to.have.status(200));
pm.test("echoes the challenge exactly", () => pm.expect(pm.response.text()).to.eql("echo123"));
```

**2. Wrong token rejected**
Same URL with `hub.verify_token=wrong-token`.
```js
pm.test("403 forbidden", () => pm.response.to.have.status(403));
```

**3. Missing token rejected**
`GET {{base_url}}/webhook/whatsapp?hub.challenge=echo123` (no `hub.verify_token` at all)
```js
pm.test("403 forbidden", () => pm.response.to.have.status(403));
```

**4. Different challenge values are echoed exactly, unmodified**
`GET {{base_url}}/webhook/whatsapp?hub.verify_token=my-verify-token&hub.challenge=some-other-value-987`
```js
pm.test("echoes exactly", () => pm.expect(pm.response.text()).to.eql("some-other-value-987"));
```

**5. Empty challenge is echoed as empty, not an error**
`GET {{base_url}}/webhook/whatsapp?hub.verify_token=my-verify-token&hub.challenge=`
```js
pm.test("status 200", () => pm.response.to.have.status(200));
pm.test("empty body", () => pm.expect(pm.response.text()).to.eql(""));
```

---

## 8. `POST /webhook/whatsapp` — 5 tests (mock delivery, real OpenAI reply)

For every request in this section: Body tab → **x-www-form-urlencoded**, with fields `To`, `From`, `Body`.

Add this **Pre-request Script** to the requests that need a *valid* signature (tests 1 and 4) — it computes the signature the way Twilio does, using Postman's built-in `CryptoJS`:

```js
const authToken = pm.environment.get("twilio_auth_token");
const url = pm.environment.get("webhook_url");
const params = {
    To: pm.environment.get("twilio_number"),
    From: "whatsapp:+972500000001",
    Body: "What is the most famous dish at U Fleku?"
};
let data = url;
Object.keys(params).sort().forEach(key => { data += key + params[key]; });
const signature = CryptoJS.HmacSHA1(data, authToken).toString(CryptoJS.enc.Base64);
pm.request.headers.upsert({ key: "X-Twilio-Signature", value: signature });
```

The request body's `To`/`From`/`Body` values must match the script's `params` **exactly** — the signature is only valid for that exact combination.

**1. Valid signature → 200, real OpenAI reply generated**
Body: `To=whatsapp:+15550001111`, `From=whatsapp:+972500000001`, `Body=What is the most famous dish at U Fleku?`
Use the pre-request script above.
```js
pm.test("status 200", () => pm.response.to.have.status(200));
```
Check the **server terminal** — a `[mock-whatsapp] to=+972500000001 text=...` log line should appear, and the text should mention the Golden Vltava Dumplings (proof the real OpenAI call used the knowledge-base fact via the region tag from section 6).

**2. Invalid signature rejected**
Same body, no pre-request script — instead manually set header `X-Twilio-Signature: not-a-real-signature`.
```js
pm.test("403 forbidden", () => pm.response.to.have.status(403));
```

**3. Missing signature header rejected**
Same body, no `X-Twilio-Signature` header at all, no pre-request script.
```js
pm.test("403 forbidden", () => pm.response.to.have.status(403));
```

**4. Unknown `To` number rejected**
Adjust the pre-request script's `To`/body to `whatsapp:+19999999999` — a number nothing is configured for.
```js
pm.test("404 not found", () => pm.response.to.have.status(404));
```

**5. GET verification token still works independently of POST signature state**
Re-run test 1 from section 7 (GET with the correct `hub.verify_token`) right after a failed POST test above.
```js
pm.test("status 200", () => pm.response.to.have.status(200));
pm.test("echoes the challenge exactly", () => pm.expect(pm.response.text()).to.eql("echo123"));
```
Confirms a rejected POST doesn't leave the webhook in a bad state for the GET handshake.