# Brief טכני ל-Claude Code — בוט קונסיירז' למלון, שלב 1

*מסמך זה מיועד להעברה ישירה ל-Claude Code כדי להתחיל בבנייה בפועל. הוא מניח שכבר קראת את התכנון האסטרטגי (`hotel_concierge_bot_plan.md`) — כאן הפירוט הוא ברמת implementation.*

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
