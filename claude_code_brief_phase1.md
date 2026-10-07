# Technical Brief for Claude Code — Hotel Concierge Bot, Stage 1

*This document is meant to be handed directly to Claude Code to start actual building. It assumes you've already read the strategic plan (`hotel_concierge_bot_plan.md`) — here the detail is at the implementation level.*

> **Plan update (see `README.md`):** "Stage 1" in this document refers to the technical core (AI engine + KnowledgeSource + the `/chat` endpoint) — and it was indeed built as described here. But the first live product this infrastructure ended up wearing is a **public website** (<https://www.window-to-the-north.co.il/chatbot/nahariya>), not the single-hotel WhatsApp channel described below. The WhatsApp channel exists in the codebase but is deferred to **"Phase 2."**

---

## Defining the scope of stage 1

A basic conversational bot for a single hotel (single-tenant at this stage, though the schema supports multiple clients from the start), answering guest questions by combining general knowledge (LLM) with local `skills` files in Markdown format. The first AI engine is **OpenAI**, with infrastructure prepared in advance for adding **Claude** right after.

---

## Stack

- **Backend:** Python, FastAPI
- **DB:** PostgreSQL (for both logging and the settings table)
- **AI Engines:** OpenAI (first), Claude (second adapter, built right after)
- **Skills storage:** `.md` files in a local folder, under git
- **Secrets:** an environment variable for the master key used to encrypt clients' API keys (never store keys in plaintext)

---

## Proposed folder structure

```
hotel-concierge-bot/
├── app/
│   ├── main.py                  # FastAPI app entrypoint
│   ├── api/
│   │   └── chat.py              # endpoint /chat
│   ├── engines/
│   │   ├── base.py              # AIEngine interface (abstract)
│   │   ├── openai_engine.py     # OpenAIAdapter
│   │   ├── claude_engine.py     # ClaudeAdapter (built right after OpenAI)
│   │   └── factory.py           # chooses engine based on client settings
│   ├── knowledge/
│   │   ├── base.py              # KnowledgeSource interface (abstract)
│   │   ├── markdown_source.py   # MarkdownFileSource (first implementation)
│   │   ├── postgres_source.py   # PostgresSource (future implementation, not in stage 1)
│   │   └── files/
│   │       ├── nahariya/
│   │       │   ├── restaurants.md
│   │       │   └── attractions.md
│   │       ├── kiryat-shmona/
│   │       │   ├── restaurants.md
│   │       │   └── attractions.md
│   │       └── eilat/
│   │           └── attractions.md
│   ├── models/
│   │   ├── hotel_settings.py    # settings table + encrypted keys
│   │   └── conversation_log.py  # anonymous logging table
│   ├── security/
│   │   └── crypto.py            # API key encryption/decryption (Fernet)
│   └── config.py
├── tests/
├── .env.example
└── requirements.txt
```

---

## Tasks, in execution order

### 1. Project skeleton
- Basic FastAPI app, `/health` endpoint
- Connection to PostgreSQL (SQLAlchemy or SQLModel)
- An `.env.example` file with the required variables (no real values)

### 2. The hotel_settings table
Columns:
- `id`
- `hotel_id` (unique, for future multi-client support)
- `ai_engine` (enum: `openai`, `claude`)
- `api_key_encrypted` (text)
- `created_at`, `updated_at`

Helper functions:
- `encrypt_key(raw_key: str) -> str`
- `decrypt_key(encrypted: str) -> str`
- Uses `cryptography.Fernet`, with the master key loaded from an environment variable (`MASTER_ENCRYPTION_KEY`), **not** from the DB.

### 3. The AI Engine abstraction layer

Unified interface (`base.py`):
```python
class AIEngine(ABC):
    @abstractmethod
    def ask(self, system_prompt: str, context: str, question: str) -> EngineResponse:
        ...
```

`EngineResponse` is a unified dataclass/pydantic model for all providers:
```python
class EngineResponse(BaseModel):
    text: str
    found_in_kb: bool
    raw_provider_response: dict | None = None  # for debugging only
```

- **OpenAIAdapter** — the first to be built. Uses OpenAI's function calling / structured output to guarantee `found_in_kb` always comes back in a consistent format.
- **ClaudeAdapter** — built right after, using the exact same interface. Uses the Claude API's tool use to achieve the same structured output.
- **factory.py** — a function `get_engine(hotel_id: str) -> AIEngine` that reads from `hotel_settings`, decrypts the key, and returns the matching adapter.

**Important:** the business-logic code (the `/chat` endpoint) only calls `AIEngine.ask(...)` through the factory — never directly to the OpenAI/Claude SDK.

### 4. The KnowledgeSource layer + Markdown source

Unified interface (`knowledge/base.py`):
```python
class KnowledgeSource(ABC):
    @abstractmethod
    def get_context(self, hotel_id: str, region: str, category: str | None = None) -> str:
        ...
```

**MarkdownFileSource** (first implementation):
- Reads all `.md` files from `app/knowledge/files/{region}/`
- Each file contains entries in YAML-frontmatter + free-text format, e.g.:
  ```markdown
  ---
  region: קריית שמונה
  category: attractions
  name: מפל תנור
  tags: [טבע, משפחות, קל]
  updated: 2026-07-13
  ---
  טיול קליל ליד המפל, מתאים למשפחות עם ילדים קטנים.
  ```
  *(Example entry shown in Hebrew — a sample of the actual stored content format, not documentation prose.)*
- Returns a single concatenated string of all entries relevant to the region, as context
- **Important:** the `/chat` endpoint only ever calls through `KnowledgeSource.get_context(...)` — it never accesses files directly. This way, the future move to `PostgresSource` is a swap of implementation, not a refactor.
- `PostgresSource` is **not** built in stage 1 — only the interface exists in advance, so the migration is clean when the time comes.

### 5. Endpoint `/chat`
Input: `{ "hotel_id": "...", "region": "...", "question": "..." }`
Logic:
1. Fetch context via `KnowledgeSource.get_context(hotel_id, region)` (no direct file access)
2. Assemble the fixed system prompt + the retrieved context
3. Call `get_engine(hotel_id).ask(...)`
4. Save an anonymous record in `conversation_log` (question, answer, `found_in_kb`, timestamp — **without** a guest identifier)
5. Return the answer to the client

### 6. System prompt (initial draft)
- Role definition: friendly concierge of Hotel X
- Instruction: "Always answer in the language the question was asked in, even if the information in the repository is written in Hebrew"
- Instruction: "If there is relevant information in the supplied content — prefer it over general knowledge, and mark `found_in_kb: true`. Otherwise answer with general knowledge and mark `found_in_kb: false`"
- Instruction for business names/addresses: also give the original Hebrew name alongside the translation, so the place can be located on Maps/Waze

### 7. Testing strategy — two separate kinds

**Unit tests (automated):**
- Test the logic (endpoint, factory, structured-output normalization) with a fake (mock) `KnowledgeSource` that returns fixed text in memory — no touching real files on disk
- Not dependent on real API keys — the `AIEngine` is also faked in these tests

**Manual/exploratory testing — a dedicated test region:**
- Add a separate test region under `app/knowledge/files/`, e.g. `prague/` — **a real, geopolitically neutral tourist city**, not a fictional city (since then there's no real competition against general knowledge) and not a politically sensitive city (so as not to trigger extra caution layers in the LLM and skew the test)
- The simulated skill contains a **distinct, fictional fact** that certainly can't come from general knowledge — e.g. the name of a made-up secret dish at a real restaurant. If the bot's answer includes that exact fictional detail, that's unambiguous proof `found_in_kb` works correctly
- Also recommended: the reverse test case — a question about the same city, in a category where the skill has **no** information, to verify `found_in_kb` returns `false` and that the answer is still valid (not "stuck")
- The test region is flagged `is_test: bool` in the `hotel_settings` table, so it's never accidentally shown to real end users, and it can be considered for exclusion from the main git repo (`.gitignore`)
- In addition: verify that switching `ai_engine` in the settings table (from `openai` to `claude`) actually changes behavior without touching code

---

## What's *not* included in this round

- No interface/conversation with the receptionist yet
- No "automatic writing to skills" layer yet
- No visual management dashboard yet — the admin form for the API key can even be a simple endpoint at this stage, not a full UI
- No smart routing between skills yet — they're all always loaded

---

## Important security notes for Claude Code

- Never log API keys, including in errors/exceptions
- `MASTER_ENCRYPTION_KEY` is loaded only from the environment, never hardcoded in code and never in git
- `.env` is in `.gitignore`
- The `/chat` API response never includes `raw_provider_response` — that's an internal debugging-only field, not part of the response to the client

---
---

# Brief טכני ל-Claude Code — בוט קונסיירז' למלון, שלב 1 *(Hebrew original)*

*מסמך זה מיועד להעברה ישירה ל-Claude Code כדי להתחיל בבנייה בפועל. הוא מניח שכבר קראת את התכנון האסטרטגי (`hotel_concierge_bot_plan.md`) — כאן הפירוט הוא ברמת implementation.*

> **עדכון תכנון (ראו `README.md`):** "שלב 1" במסמך הזה מתייחס לליבה הטכנית (AI engine + KnowledgeSource + endpoint `/chat`) — וזו אכן נבנתה כפי שתואר כאן. אך המוצר החי הראשון שהתשתית הזו הולבשה עליו הוא **אתר ציבורי** (<https://www.window-to-the-north.co.il/chatbot/nahariya>), לא ערוץ וואטסאפ למלון בודד כמתואר למטה. ערוץ הוואטסאפ למלון קיים בקוד אך נדחה ל-**"Phase 2"**.

---

## הגדרת היקף שלב 1

בוט שיחה בסיסי למלון בודד (single-tenant בשלב זה, אך הסכימה תומכת ריבוי לקוחות מההתחלה), שעונה על שאלות אורחים באמצעות שילוב של ידע כללי (LLM) וקבצי `skills` מקומיים בפורמט Markdown. מנוע ה-AI הראשון הוא **OpenAI**, עם תשתית מוכנה מראש להוספת **Claude** מיד אחרי.

---

## Stack

- **Backend:** Python, FastAPI
- **DB:** PostgreSQL (גם ל-logging וגם לטבלת ה-settings)
- **AI Engines:** OpenAI (ראשון), Claude (adapter שני, נבנה ישר אחרי)
- **Skills storage:** קבצי `.md` בתיקייה מקומית, תחת git
- **Secrets:** environment variable למפתח ה-master להצפנת מפתחות API של לקוחות (לא לשמור מפתחות בגלוי)

---

## מבנה תיקיות מוצע

```
hotel-concierge-bot/
├── app/
│   ├── main.py                  # FastAPI app entrypoint
│   ├── api/
│   │   └── chat.py              # endpoint /chat
│   ├── engines/
│   │   ├── base.py              # ממשק AIEngine (abstract)
│   │   ├── openai_engine.py     # OpenAIAdapter
│   │   ├── claude_engine.py     # ClaudeAdapter (נבנה מיד אחרי OpenAI)
│   │   └── factory.py           # בחירת engine לפי הגדרות הלקוח
│   ├── knowledge/
│   │   ├── base.py              # ממשק KnowledgeSource (abstract)
│   │   ├── markdown_source.py   # MarkdownFileSource (מימוש ראשון)
│   │   ├── postgres_source.py   # PostgresSource (מימוש עתידי, לא בשלב 1)
│   │   └── files/
│   │       ├── nahariya/
│   │       │   ├── restaurants.md
│   │       │   └── attractions.md
│   │       ├── kiryat-shmona/
│   │       │   ├── restaurants.md
│   │       │   └── attractions.md
│   │       └── eilat/
│   │           └── attractions.md
│   ├── models/
│   │   ├── hotel_settings.py    # טבלת הגדרות + מפתחות מוצפנים
│   │   └── conversation_log.py  # טבלת לוגים אנונימית
│   ├── security/
│   │   └── crypto.py            # הצפנה/פענוח מפתחות API (Fernet)
│   └── config.py
├── tests/
├── .env.example
└── requirements.txt
```

---

## משימות, לפי סדר ביצוע

### 1. שלד הפרויקט
- FastAPI app בסיסי, endpoint `/health`
- חיבור ל-PostgreSQL (SQLAlchemy או SQLModel)
- קובץ `.env.example` עם המשתנים הנדרשים (ללא ערכים אמיתיים)

### 2. טבלת hotel_settings
עמודות:
- `id`
- `hotel_id` (unique, למקרה של ריבוי לקוחות בעתיד)
- `ai_engine` (enum: `openai`, `claude`)
- `api_key_encrypted` (text)
- `created_at`, `updated_at`

פונקציות עזר:
- `encrypt_key(raw_key: str) -> str`
- `decrypt_key(encrypted: str) -> str`
- שימוש ב-`cryptography.Fernet`, עם master key שנטען מ-environment variable (`MASTER_ENCRYPTION_KEY`), **לא** מה-DB.

### 3. שכבת המעטפת ל-AI Engine

ממשק אחיד (`base.py`):
```python
class AIEngine(ABC):
    @abstractmethod
    def ask(self, system_prompt: str, context: str, question: str) -> EngineResponse:
        ...
```

`EngineResponse` הוא dataclass/pydantic model אחיד לכל הספקים:
```python
class EngineResponse(BaseModel):
    text: str
    found_in_kb: bool
    raw_provider_response: dict | None = None  # לדיבוג בלבד
```

- **OpenAIAdapter** — ראשון להיבנות. שימוש ב-function calling / structured output של OpenAI כדי להבטיח שה-`found_in_kb` תמיד חוזר בפורמט אחיד.
- **ClaudeAdapter** — נבנה מיד אחרי, באותו ממשק בדיוק. שימוש ב-tool use של Claude API להשגת אותו structured output.
- **factory.py** — פונקציה `get_engine(hotel_id: str) -> AIEngine` שקוראת מ-`hotel_settings`, מפענחת את המפתח, ומחזירה את ה-adapter המתאים.

**חשוב:** קוד הלוגיקה העסקית (ה-endpoint `/chat`) קורא רק ל-`AIEngine.ask(...)` דרך ה-factory — אף פעם לא ישירות ל-OpenAI/Claude SDK.

### 4. שכבת KnowledgeSource + Markdown source

ממשק אחיד (`knowledge/base.py`):
```python
class KnowledgeSource(ABC):
    @abstractmethod
    def get_context(self, hotel_id: str, region: str, category: str | None = None) -> str:
        ...
```

**MarkdownFileSource** (מימוש ראשון):
- קורא את כל קבצי ה-`.md` מתוך `app/knowledge/files/{region}/`
- כל קובץ מכיל entries בפורמט YAML frontmatter + תוכן חופשי, למשל:
  ```markdown
  ---
  region: נהריה
  category: attractions
  name: מפל תנור
  tags: [טבע, משפחות, קל]
  updated: 2026-07-13
  ---
  טיול קליל ליד המפל, מתאים למשפחות עם ילדים קטנים.
  ```
- מחזיר מחרוזת מאוחדת (concat) של כל ה-entries הרלוונטיים לאזור, כ-context
- **חשוב:** ה-endpoint `/chat` קורא אך ורק דרך `KnowledgeSource.get_context(...)` — אף פעם לא ניגש לקבצים ישירות. כך המעבר העתידי ל-`PostgresSource` הוא swap של מימוש, לא refactor.
- `PostgresSource` **לא** נבנה בשלב 1 — רק ה-interface קיים מראש, כדי שהמעבר יהיה נקי כשיגיע הזמן.

### 5. Endpoint `/chat`
קלט: `{ "hotel_id": "...", "region": "...", "question": "..." }`
לוגיקה:
1. שליפת context דרך `KnowledgeSource.get_context(hotel_id, region)` (לא ניגש לקבצים ישירות)
2. הרכבת system prompt קבוע + ה-context שהתקבל
3. קריאה ל-`get_engine(hotel_id).ask(...)`
4. שמירת רשומה אנונימית ב-`conversation_log` (שאלה, תשובה, `found_in_kb`, timestamp — **בלי** מזהה אורח)
5. החזרת התשובה ל-client

### 6. System prompt (טיוטה ראשונית)
- הגדרת תפקיד: קונסיירז' ידידותי של מלון X
- הנחיה: "ענה תמיד בשפה שבה נשאלת השאלה, גם אם המידע במאגר כתוב בעברית"
- הנחיה: "אם יש מידע רלוונטי בתוכן שסופק — העדף אותו על ידע כללי, וסמן `found_in_kb: true`. אחרת ענה מידע כללי וסמן `found_in_kb: false`"
- הנחיה לשמות עסקים/כתובות: לתת גם את השם המקורי בעברית לצד תרגום, כדי שאפשר יהיה לאתר את המקום ב-Maps/Waze

### 7. אסטרטגיית בדיקות — שני סוגים נפרדים

**Unit tests (אוטומטיים):**
- בדיקת הלוגיקה (endpoint, factory, נירמול structured output) עם `KnowledgeSource` מזויף (mock) שמחזיר טקסט קבוע בזיכרון — לא נוגעים בקבצים אמיתיים על הדיסק
- לא תלויים ב-API keys אמיתיים — גם ה-`AIEngine` מזויף בטסטים אלה

**בדיקה ידנית/exploratory — אזור בדיקה ייעודי:**
- מוסיפים אזור בדיקה נפרד תחת `app/knowledge/files/`, למשל `prague/` — **עיר תיירותית אמיתית וניטרלית geopolitically**, לא עיר בדיונית (כי אז אין תחרות אמיתית מול ידע כללי) ולא עיר רגישה פוליטית (כדי לא להפעיל שכבות זהירות נוספות אצל ה-LLM ולהטות את הטסט)
- ה-skill המדומה מכיל **עובדה בדיונית ומובחנת** שבוודאות לא יכולה להגיע מידע כללי — למשל שם מנה סודית פיקטיבית במסעדה קיימת. אם תשובת הבוט כוללת את הפרט הבדיוני הזה בדיוק, יש הוכחה חד-משמעית ש-`found_in_kb` עובד נכון
- מומלץ גם test case הפוך: שאלה על אותה עיר, בקטגוריה שבה **אין** מידע ב-skill, כדי לוודא ש-`found_in_kb` חוזר `false` ושהתשובה עדיין תקינה (לא "נתקעת")
- אזור הבדיקה מסומן `is_test: bool` בטבלת `hotel_settings`, כדי שלעולם לא יוצג בטעות למשתמשי קצה אמיתיים, ואפשר לשקול להוציא אותו מ-git הראשי (`.gitignore`)
- בנוסף: לוודא שהחלפת `ai_engine` בטבלת ה-settings (מ-`openai` ל-`claude`) משנה את ההתנהגות בפועל בלי לגעת בקוד

---

## מה *לא* נכנס בסבב הזה

- אין עדיין ממשק/שיחה עם פקידת הקבלה
- אין עדיין שכבת "כתיבה אוטומטית ל-skills"
- אין עדיין דשבורד ניהול ויזואלי — טופס admin ל-API key יכול להיות אפילו endpoint פשוט בשלב זה, לא UI מלא
- אין עדיין routing חכם בין skills — כולם נטענים תמיד

---

## הערות אבטחה חשובות ל-Claude Code

- לעולם לא לרשום מפתחות API ב-logs, כולל בשגיאות/exceptions
- `MASTER_ENCRYPTION_KEY` נטען אך ורק מ-environment, אף פעם לא מקודד בקוד (hardcoded) ואף פעם לא ב-git
- `.env` בקובץ `.gitignore`
- תשובת ה-API של `/chat` אף פעם לא כוללת את `raw_provider_response` — זה שדה פנימי לדיבוג בלבד, לא חלק מהתגובה ל-client
