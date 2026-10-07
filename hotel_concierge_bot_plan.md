# Hotel Concierge Bot — Staged Plan

*This document summarizes the plan developed together with the hotel owner and his receptionist, for building a bot that recommends nearby activities to guests and learns from the field over time.*

> **Plan update (see `README.md`):** After this document was written, it was decided that the first live product (the actual "Phase 1") would be a **public website** — a regional-info chatbot, currently live at <https://www.window-to-the-north.co.il/chatbot/nahariya> — rather than a single-hotel WhatsApp bot. The vision described in this document (stages 1-4, including the receptionist feedback loop) hasn't been cancelled — it's deferred to **"Phase 2"**, to be built on top of the existing infrastructure (the AI-engine and KnowledgeSource abstraction layers described here are already implemented in code and also power the current website version).

---

## The idea in few lines

A bot that accompanies a guest throughout their stay — recommending restaurants, trips, and attractions, answering allergen questions, and taking requests addressed to the hotel — built on general knowledge from the internet combined with unique local information gathered over time from the receptionist. In the first stage the bot operates as a WhatsApp channel (with a possible future additional channel, such as a page on the hotel's website), so it keeps only the minimum information necessary about the guest — phone number and basic stay details — and deletes it automatically once the stay ends.

---

## Core principles (unchanged across stages)

- **It's permitted to store stay-related information; it's forbidden to store identifying information about the guest as a person** — in the first stage the bot operates as a WhatsApp channel (a channel via the hotel's website may be added later), so it stores the guest's phone number in order to manage the conversation, as well as the stay details themselves — such as check-in and check-out dates — in order to give relevant recommendations throughout the stay. **No** identifying detail about the guest as a person (name, ID number, etc.) is ever stored linked to the conversation content. The phone number and stay details are deleted automatically once the stay ends (checkout) — they are never kept permanently. The conversation log (`conversation_log`) remains fully anonymous as before, and is never linked to the guest's phone number.
- **The receptionist doesn't need to know any technical concept.** She just answers questions in free-form language — Hebrew or English — exactly as she would answer a colleague.
- **The system writes to itself.** All the "structuring" (where to store information, how to phrase it) is done by a separate AI layer, not by a human.
- **A single source of truth, not multilingual.** The skills content is stored in one language (Hebrew), and the model translates it "in real time" into the guest's language on every conversation.

---

## Stage 1 — Technical core (MVP)

**Goal:** confirm the basic idea works — a bot that answers well, and recognizes when it's missing information.

### What's included
- **A fixed system prompt** — defines the bot as the hotel's friendly concierge, with an explicit instruction: "If there is relevant information in the skills files — prefer it over general knowledge. Always answer in the guest's language."
- **Skills folder** — separate `.md` files per domain, e.g.:
  ```
  skills/
    hiking.md          (nature hikes)
    restaurants.md      (restaurants + allergens)
    attractions.md      (attractions and activities)
    nightlife.md        (evening entertainment)
  ```
  At first, nearly empty — just structure, without much content.
- **A basic chat endpoint** — receives a question from a guest, injects all the skills files as context (they're small at this stage, no need for smart routing), sends it to the LLM, and returns an answer.
- **A response in structured format**, including a field like `found_in_kb: true/false` — to identify when the bot answered using general knowledge only.
- **Anonymous logging** — every conversation (question + answer, without guest identification) is stored in a table, mainly for manual review at this stage.

### Abstraction layer for the AI engine (important to build from day one)

So that every client (hotel) can choose their preferred AI engine — Claude, OpenAI, Gemini, etc. — without touching code, it's worth building an abstraction layer from the start, between the bot's logic and the specific provider:

- **A unified interface** that the bot's logic talks to exclusively — e.g. a function like `engine.ask(system_prompt, context, question) -> {text, found_in_kb, ...}`. No business logic code knows which provider is behind the interface.
- **A separate adapter for each provider** — `ClaudeAdapter`, `OpenAIAdapter`, `GeminiAdapter`, etc., each translating from the unified interface to that provider's specific API.
- **Normalizing structured output** — this is usually the "messiest" point in such an abstraction layer, because each provider implements function calling / JSON mode differently. It's worth investing time here so the `found_in_kb` field and other structured fields come back in exactly the same format, no matter which provider is operating behind the scenes.
- **Choosing the engine via configuration** — an environment variable or a field in the client's settings (`ai_engine: "claude" | "openai" | "gemini"`), no code change needed to switch engines for a given client.

Building this doesn't add much time if done from the start (instead of calling one provider's API directly from the logic, you simply call through the interface) — but if it's skipped now and added later, it becomes a refactor that touches every place an LLM is called.

### What's *not* included at this stage
- No interface for the receptionist yet.
- No dashboard or management yet.
- No agreements with businesses yet — everything is based on general knowledge + whatever you fill in manually for testing.

### How to verify it works
Manually send the bot a few real questions (in Hebrew, English), check that the answers are reasonable, and that when relevant skill information exists it's genuinely preferred over general knowledge.

---

## Stage 2 — The receptionist feedback loop

**Goal:** close the loop — the bot actively "learns" from her knowledge, without her needing to understand anything technical.

### What's included
- **A separate conversation with her** (can be the same technical interface, just a different prompt) — the bot shows her a question a guest asked that had no internal information (`found_in_kb: false`), and she answers freely.
- **A "write to skill" layer** — a separate LLM call that receives:
  - the original question
  - her free-form answer
  - the current content of the relevant skills files

  and returns: which skill this belongs to, whether it's a new addition or an update to an existing entry (to prevent duplicates and contradictions over time), and a tidy phrasing to add.
- **Partial quality control, for the allergens category only** — here, and only here, it's worth considering a brief yes/no confirmation from her before final saving, because of the medical sensitivity.

### What's *not* included yet
- No visual dashboard yet — the conversation with her can be in a simple format (e.g. WhatsApp or a minimal chat interface).
- No smart file search yet — they're still small enough to load fully as context.

---

## Stage 3 — Management and oversight tools (for humans, not AI)

**Goal:** give you and the hotel owner transparency into what's happening, without involving the receptionist.

### What's included
- **Skills files in git** — every change is a commit. You or the hotel owner can review the diff occasionally and catch mistakes or drift.
- **A lightweight dashboard (optional)** — a conversations table filterable by `found_in_kb: false`, to see which questions still aren't answered well.
- **Starting smart routing** — once the number of skills and amount of content grows and no longer fits comfortably in the context window, add a lightweight classification step (a cheap LLM) that chooses which skills to load per question, instead of loading all of them.

---

## Stage 4 — Business extensions (only after the core proves its value)

- **Agreements with local businesses** — discounts/perks for guests who arrive via the bot. This stage requires work with the businesses themselves, not just technical work.
- **Internal requests to the hotel** — extra towels, breakfast changes, etc. This is really a separate product (more queue/ticketing, less retrieval) and should be planned as an add-on to the core, not part of it.
- **A map view** and sorting by location.
- **A more structured questionnaire for businesses** that join on their own (not only information passed through the receptionist).

### An abstraction layer for the knowledge source too (KnowledgeSource)

On exactly the same principle as the AI-engine abstraction layer — the business logic code shouldn't know whether the information comes from MD files or from a DB. A unified interface, e.g. `KnowledgeSource.get_context(hotel_id, region, category) -> str`, with a first implementation `MarkdownFileSource` and a future implementation `PostgresSource`. That way, the move to a DB, when the time comes, is **a single implementation swap**, not a refactor touching the whole system.

This is especially important here because — once the system grows — **the real value of the project isn't the code but the skills repository itself** (the accumulated regional information about restaurants, attractions, and trips). So it's worth planning the "migration moment" to a DB already now, so that it's cheap and technical and doesn't involve redoing manual work.

### Structured format inside the MD files (YAML frontmatter)

So that the future move to a DB doesn't require another LLM to extract facts from free text, the "writing" layer (the one that writes based on the conversation with the receptionist) needs to produce every entry already in a structured format inside the MD:

```markdown
---
region: נהריה
category: attractions
name: נחל כזיב
tags: [טבע, משפחות, טיול בינוני עד קשה]
updated: 2026-07-13
---
טיול טבע, מתאים למשפחות עם ילדים יחסית גדולים.
```

*(Example entry shown in Hebrew — this is a sample of the actual stored content format, not documentation prose; see "Core principles" above on why the knowledge content itself stays Hebrew-only.)*

It's still a regular MD file, readable in a git diff, but every entry is effectively already a future DB row with a clear schema. The move to a DB becomes a script that reads YAML and inserts rows — no LLM needed at all, because the structure already exists.

### Folder convention by region and category

Because regional information is actually a central axis (restaurants in Nahariya, attractions in Eilat, etc.), it's worth building the skills folder along these dimensions from the start — this also maps directly to a future schema (`region` + `category` as columns), and gives "free" routing by the hotel's region, without needing to load all regions for every question:

```
skills/
  nahariya/
    restaurants.md
    attractions.md
  kiryat-shmona/
    restaurants.md
    attractions.md
  eilat/
    attractions.md
```

### Actually triggering the migration

- A feature flag at the `hotel_settings` level, e.g. `knowledge_source: file | db` — just like `ai_engine` — to migrate one client at a time, not all-or-nothing.
- A one-time script that reads the YAML frontmatter from all the MD files and inserts it into the DB — a matter of minutes, not a project, because the information is already structured.
- It's worth considering keeping the git history of the MD files even after the migration, as an archive/audit trail, and perhaps even periodically exporting a backup from the DB back to MD for transparency and human readability.

| Component | Suggestion | Note |
|---|---|---|
| Backend | Python (FastAPI) | Lightweight, suited to a simple API endpoint |
| LLM | An abstraction layer over Claude API / OpenAI / Gemini | Unified interface + adapter per provider, so the client can choose an engine without a code change |
| Skills storage | `.md` files (with YAML frontmatter) in a folder, under git — via the `KnowledgeSource` abstraction layer | No DB needed at this stage; the future move is a swap of implementation, not a refactor |
| Conversation logging | SQLite or plain PostgreSQL | One table: question, answer, timestamp, found_in_kb |
| Hosting | One small server (a single VM) is enough to start | No real load yet |

**Important point:** in stages 1-2 there's no need at all for a vector database or semantic search — the amount of content is small enough that fully loading all the skills as context works great. A smarter search layer (possibly including embeddings, if desired) is only relevant if and when the skills files grow significantly.

---

## Stage 1 time estimate

| Component | Estimate |
|---|---|
| Basic endpoint + system prompt + loading skills | One workday |
| AI-engine abstraction layer (interface + one adapter, e.g. Claude) | One to one and a half days |
| Structured output + normalization (`found_in_kb` etc.) | Half a day |
| Anonymous conversation logging | Half a day |
| Manual testing, tuning the system prompt | One to two days |
| **Total for stage 1 (with a single engine only)** | **About 4-5 workdays** |
| Adding an adapter for a second provider (e.g. OpenAI), to test the layer | One to two more days |

This estimate assumes independent work with tools like Claude Code for planning and writing code, with no need for an approval cycle with a third party. If stage 1 is scoped down (a single AI engine, no abstraction layer yet) you could get started within two to three days — but then the abstraction layer comes in as an "addition" at a later stage, rather than an integral part from the start.

---

## Priority summary

1. Technical core that answers well and identifies gaps (stage 1)
2. Feedback loop with the receptionist, including the automatic writing layer (stage 2)
3. Lightweight oversight tools for you and the hotel owner (stage 3)
4. Business extensions — only after the basic value is proven (stage 4)

---
---

# בוט קונסיירז' למלון — תכנון שלבים *(Hebrew original)*

*מסמך זה מסכם את התכנון שגובש עם בעל המלון ופקידת הקבלה שלו, לבניית בוט שממליץ לאורחים על פעילויות בסביבה ולומד מהשטח לאורך זמן.*

> **עדכון תכנון (ראו `README.md`):** לאחר כתיבת מסמך זה הוחלט שהמוצר החי הראשון (ה-"Phase 1" בפועל) יהיה **אתר אינטרנט ציבורי** — צ'אטבוט מידע אזורי, חי כרגע ב-<https://www.window-to-the-north.co.il/chatbot/nahariya> — ולא בוט וואטסאפ למלון בודד. החזון המתואר במסמך הזה (שלבים 1-4, כולל לולאת המשוב מפקידת הקבלה) לא בוטל — הוא נדחה ל-**"Phase 2"**, וייבנה מעל התשתית הקיימת (שכבות ה-AI engine וה-KnowledgeSource שתוארו כאן כבר מומשו בקוד ומשמשות גם את גרסת האתר הנוכחית).

---

## הרעיון בשורה אחת

בוט שילווה אורח לאורך החופשה — ימליץ על מסעדות, טיולים ואטרקציות, יענה על שאלות אלרגנים, ויקבל בקשות מהמלון — ויתבסס על ידע כללי מהאינטרנט בשילוב מידע מקומי ייחודי שנאסף לאורך זמן מפקידת הקבלה. בשלב הראשון הבוט פועל כערוץ וואטסאפ (עם אפשרות עתידית לערוץ נוסף, כמו עמוד באתר המלון), ולכן שומר מינימום מידע הכרחי על האורח בלבד — מספר טלפון ופרטי חופשה בסיסיים — ומוחק אותו אוטומטית עם סיום השהות.

---

## עקרונות ליבה (לא משתנים בין השלבים)

- **מותר לשמור מידע על החופשה, אסור לשמור מידע מזהה על האורח עצמו** — בשלב הראשון הבוט פועל כערוץ וואטסאפ (ייתכן שיתווסף בעתיד גם ערוץ דרך אתר המלון), ולכן הוא שומר את מספר הטלפון של האורח כדי לנהל את השיחה, וכן את פרטי החופשה עצמה — כגון תאריכי צ'ק-אין וצ'ק-אאוט — כדי לתת המלצות רלוונטיות לאורך השהות. **לא** נשמר שום פרט מזהה על האורח כאדם (שם, תעודת זהות וכו') מקושר לתוכן השיחה. הטלפון ופרטי החופשה נמחקים אוטומטית עם סיום השהות (checkout) — לא נשמרים לצמיתות. לוג השיחות (`conversation_log`) נשאר אנונימי לחלוטין כפי שהיה, ואינו מקושר לטלפון האורח.
- **פקידת הקבלה לא צריכה לדעת שום מושג טכני.** היא רק עונה על שאלות בשפה חופשית — עברית או אנגלית — בדיוק כמו שהיא הייתה עונה לעמית לעבודה.
- **המערכת כותבת לעצמה.** כל ה"מבנה" (איפה לשמור מידע, איך לנסח אותו) נעשה על ידי שכבת AI נפרדת, לא על ידי בן אדם.
- **מקור אמת יחיד, לא רב־לשוני.** תוכן ה־skills נשמר בשפה אחת (עברית), והמודל מתרגם "בזמן אמת" לשפת האורח בכל שיחה.

---

## שלב 1 — הליבה הטכנית (MVP)

**מטרה:** לוודא שהרעיון הבסיסי עובד — בוט שעונה טוב, ומזהה מתי חסר לו מידע.

### מה נכנס
- **System prompt קבוע** — מגדיר את הבוט כקונסיירז' ידידותי של המלון, עם הנחיה מפורשת: "אם יש מידע רלוונטי בקבצי ה־skills — העדף אותו על ידע כללי. תמיד ענה בשפת האורח."
- **תיקיית skills** — קבצי `.md` נפרדים לפי תחום, למשל:
  ```
  skills/
    hiking.md          (טיולי טבע)
    restaurants.md      (מסעדות + אלרגנים)
    attractions.md      (אטרקציות ופעילויות)
    nightlife.md        (בילויים בערב)
  ```
  בהתחלה כמעט ריקים — רק מבנה, בלי הרבה תוכן.
- **Endpoint שיחה בסיסי** — מקבל שאלה מאורח, מזריק את כל קבצי ה־skills כ־context (הם קטנים בשלב זה, אין צורך ב־routing חכם), שולח ל־LLM, מחזיר תשובה.
- **תשובה ב־structured format**, כולל שדה כמו `found_in_kb: true/false` — כדי לזהות מתי הבוט ענה מידע כללי בלבד.
- **Logging אנונימי** — כל שיחה (שאלה + תשובה, בלי זיהוי אורח) נשמרת בטבלה, בעיקר לבדיקה ידנית בשלב זה.

### שכבת מעטפת למנוע ה־AI (חשוב לבנות מהיום הראשון)

כדי שכל לקוח (מלון) יוכל לבחור את מנוע ה־AI המועדף עליו — Claude, OpenAI, Gemini וכו' — בלי לגעת בקוד, כדאי לבנות מהתחלה שכבת הפשטה (abstraction layer) בין הלוגיקה של הבוט לבין הספק הספציפי:

- **ממשק אחיד** (interface) שהלוגיקה של הבוט מדברת איתו בלבד — למשל פונקציה כמו `engine.ask(system_prompt, context, question) -> {text, found_in_kb, ...}`. שום קוד עסקי לא יודע איזה ספק עומד מאחורי הממשק.
- **מתאם (adapter) נפרד לכל ספק** — `ClaudeAdapter`, `OpenAIAdapter`, `GeminiAdapter` וכו', כל אחד מתרגם מהממשק האחיד ל־API הספציפי של אותו ספק.
- **נירמול של structured output** — זו בדרך כלל הנקודה הכי "מלוכלכת" בשכבת מעטפת כזו, כי כל ספק מממש function calling / JSON mode אחרת. שווה להשקיע כאן זמן כדי שהשדה `found_in_kb` ושאר השדות המובנים יחזרו באותו פורמט בדיוק, לא משנה איזה ספק פועל מאחורי הקלעים.
- **בחירת מנוע דרך קונפיגורציה** — משתנה סביבה או שדה בהגדרות הלקוח (`ai_engine: "claude" | "openai" | "gemini"`), לא צריך שינוי קוד כדי להחליף מנוע ללקוח נתון.

הבנייה הזו לא מוסיפה הרבה זמן אם עושים אותה מההתחלה (במקום לקרוא ל־API של ספק אחד ישירות מהלוגיקה, פשוט קוראים דרך הממשק) — אבל אם מדלגים עליה עכשיו ומחליטים להוסיף אותה מאוחר יותר, זה refactor שמצריך לגעת בכל מקום שבו יש קריאה ל־LLM.

### מה *לא* נכנס בשלב הזה
- אין עדיין ממשק לפקידת הקבלה.
- אין עדיין דשבורד או ניהול.
- אין עדיין הסכמים עם עסקים — הכול מבוסס ידע כללי + מה שתמלאו ידנית לצורך בדיקה.

### איך בודקים שזה עובד
שולחים לבוט ידנית כמה שאלות אמיתיות (בעברית, אנגלית), בודקים שהתשובות סבירות, ושכאשר יש מידע ב־skill רלוונטי הוא באמת מועדף על פני ידע כללי.

---

## שלב 2 — לולאת המשוב מפקידת הקבלה

**מטרה:** לסגור את המעגל — הבוט "לומד" באופן פעיל מהידע שלה, בלי שהיא צריכה להבין שום דבר טכני.

### מה נכנס
- **שיחה נפרדת איתה** (יכולה להיות אותו ממשק טכני, רק prompt אחר) — הבוט מציג לה שאלה שאורח שאל ולא היה עליה מידע פנימי (`found_in_kb: false`), והיא עונה בחופשיות.
- **שכבת "כתיבה ל־skill"** — קריאת LLM נפרדת שמקבלת:
  - השאלה המקורית
  - התשובה החופשית שלה
  - התוכן הנוכחי של קובצי ה־skills הרלוונטיים

  ומחזירה: לאיזה skill זה שייך, האם זו תוספת חדשה או עדכון לרשומה קיימת (כדי למנוע כפילויות וסתירות עם הזמן), וניסוח מסודר להוספה.
- **בקרת איכות חלקית לקטגוריית אלרגנים בלבד** — כאן, ורק כאן, שווה לשקול אישור קצר של כן/לא ממנה לפני שמירה סופית, בגלל הרגישות הרפואית.

### מה *לא* נכנס עדיין
- אין עדיין דשבורד ויזואלי — השיחה איתה יכולה להיות בפורמט פשוט (למשל וואטסאפ או ממשק צ'אט מינימלי).
- אין עדיין חיפוש חכם בקבצים — הם עדיין קטנים מספיק לטעינה מלאה כ־context.

---

## שלב 3 — כלים לניהול ופיקוח (לא ל־AI, לבני אדם)

**מטרה:** לתת לך ולבעל המלון שקיפות על מה שקורה, בלי לערב את פקידת הקבלה.

### מה נכנס
- **קבצי ה־skills ב־git** — כל שינוי הוא commit. אתה או בעל המלון יכולים לעבור על ה־diff מדי פעם ולתפוס טעויות או דריפט.
- **דשבורד קליל (אופציונלי)** — טבלת שיחות עם סינון לפי `found_in_kb: false`, כדי לראות אילו שאלות עדיין לא נענות טוב.
- **התחלת routing חכם** — כשמספר ה־skills וכמות התוכן גדלים ולא נכנסים בנוחות ל־context window, מוסיפים שלב סיווג קליל (LLM זול) שבוחר אילו skills לטעון לכל שאלה, במקום לטעון את כולם.

---

## שלב 4 — הרחבות עסקיות (רק אחרי שהליבה מוכיחה ערך)

- **הסכמים עם עסקים מקומיים** — הנחות/צ'ופרים לאורחים שמגיעים דרך הבוט. זה שלב שדורש גם עבודה מול העסקים, לא רק טכנית.
- **בקשות פנימיות מהמלון** — מגבות נוספות, שינויים בארוחת בוקר וכו'. זה בעצם מוצר נפרד (יותר תור/טיקטים, פחות retrieval) וכדאי לתכנן אותו כתוסף על הליבה, לא כחלק ממנה.
- **תצוגת מפה** ומיון לפי מיקום.
- **שאלון מובנה יותר לעסקים** שמצטרפים בעצמם (לא רק מידע שעובר דרך פקידת הקבלה).

### שכבת מעטפת גם למקור הידע (KnowledgeSource)

באותו עיקרון בדיוק כמו שכבת המעטפת ל-AI engine — הקוד העסקי לא אמור לדעת אם המידע מגיע מקבצי MD או מ-DB. ממשק אחיד, למשל `KnowledgeSource.get_context(hotel_id, region, category) -> str`, עם מימוש ראשון `MarkdownFileSource` ומימוש עתידי `PostgresSource`. כך המעבר ל-DB, כשיגיע הזמן, הוא **swap של מימוש אחד**, לא refactor שנוגע בכל המערכת.

זה חשוב במיוחד כאן כי — ברגע שהמערכת גדלה — **הערך האמיתי של הפרויקט הוא לא הקוד אלא מאגר ה-skills עצמו** (המידע האזורי המצטבר על מסעדות, אטרקציות וטיולים). לכן שווה לתכנן את "רגע המעבר" ל-DB כבר עכשיו, כדי שהוא יהיה זול וטכני ולא כרוך בעבודה ידנית מחדש.

### פורמט מובנה בתוך קבצי ה-MD (YAML frontmatter)

כדי שהמעבר העתידי ל-DB לא ידרוש שוב LLM שיחלץ עובדות מטקסט חופשי, שכבת ה"כתיבה" (זו שכותבת מתוך השיחה עם פקידת הקבלה) צריכה לייצר כל entry כבר בפורמט מובנה בתוך ה-MD:

```markdown
---
region: נהריה
category: attractions
name: נחל כזיב
tags: [טבע, משפחות, טיול בינוני עד קשה]
updated: 2026-07-13
---
טיול טבע, מתאים למשפחות עם ילדים יחסית גדולים.
```

זה עדיין קובץ MD רגיל וקריא ל-git diff, אבל כל entry הוא בעצם כבר שורת DB עתידית עם schema ברור. המעבר ל-DB הופך לסקריפט שקורא YAML ומכניס שורות — בלי צורך ב-LLM כלל, כי המבנה כבר קיים.

### מוסכמת תיקיות לפי אזור וקטגוריה

בגלל שהמידע האזורי הוא בעצם ציר מרכזי (מסעדות בנהריה, אטרקציות באילת וכו'), כדאי לבנות את תיקיית ה-skills לפי הממדים האלה מההתחלה — זה גם ממפה ישירות ל-schema עתידי (`region` + `category` כעמודות), וגם נותן routing "בחינם" לפי אזור המלון, בלי צורך לטעון את כל האזורים בכל שאלה:

```
skills/
  nahariya/
    restaurants.md
    attractions.md
  kiryat-shmona/
    restaurants.md
    attractions.md
  eilat/
    attractions.md
```

### הפעלת המעבר בפועל

- Feature flag ברמת `hotel_settings`, למשל `knowledge_source: file | db` — בדיוק כמו `ai_engine` — כדי לעבור לקוח אחד בכל פעם, לא הכול־או־כלום.
- Script חד־פעמי שקורא את ה-YAML frontmatter מכל קבצי ה-MD ומכניס ל-DB — עבודה של דקות, לא פרויקט, כי המידע כבר מובנה.
- שווה לשקול לשמור את ה-git history של קבצי ה-MD גם אחרי המעבר, כארכיון/audit trail, ואולי אפילו לייצא גיבוי תקופתי מה-DB בחזרה ל-MD לצורך שקיפות וקריאה אנושית.

| רכיב | הצעה | הערה |
|---|---|---|
| Backend | Python (FastAPI) | קליל, מתאים ל־API endpoint פשוט |
| LLM | שכבת מעטפת (abstraction layer) מעל Claude API / OpenAI / Gemini | ממשק אחיד + adapter לכל ספק, כדי שהלקוח יוכל לבחור מנוע בלי שינוי קוד |
| אחסון skills | קבצי `.md` (עם YAML frontmatter) בתיקייה, תחת git — דרך שכבת מעטפת `KnowledgeSource` | לא צריך DB בשלב הזה; המעבר עתידי הוא swap של מימוש, לא refactor |
| Logging שיחות | SQLite או PostgreSQL פשוט | טבלה אחת: שאלה, תשובה, timestamp, found_in_kb |
| Hosting | שרת קטן אחד (VM בודד) מספיק להתחלה | אין עדיין עומס אמיתי |

**נקודה חשובה:** בשלב 1-2 אין שום צורך בבסיס נתונים וקטורי או בחיפוש סמנטי — כמות התוכן קטנה מספיק שטעינה מלאה של כל ה־skills כ־context עובדת מצוין. שכבת חיפוש חכמה יותר (כולל אולי embeddings, אם תרצו) רלוונטית רק אם וכאשר קבצי ה־skills יגדלו משמעותית.

---

## הערכת זמן לשלב 1

| רכיב | הערכה |
|---|---|
| Endpoint בסיסי + system prompt + טעינת skills | יום עבודה אחד |
| שכבת מעטפת ל־AI engine (ממשק + adapter אחד, למשל Claude) | יום עד יום וחצי |
| Structured output + נירמול (`found_in_kb` וכו') | חצי יום |
| Logging אנונימי לשיחות | חצי יום |
| בדיקות ידניות, כוונון ה־system prompt | יום עד יומיים |
| **סה"כ שלב 1 (עם מנוע אחד בלבד)** | **כ־4-5 ימי עבודה** |
| הוספת adapter לספק שני (למשל OpenAI), לבדיקת השכבה | עוד יום־יומיים |

ההערכה מניחה עבודה עצמאית עם כלים כמו Claude Code לתכנון ולכתיבת קוד, וללא צורך בסבב אישורים מול צד שלישי. אם שלב 1 מוגדר בצמצום (מנוע AI יחיד, בלי מעטפת עדיין) אפשר לצאת לדרך תוך יומיים־שלושה — אבל אז שכבת המעטפת נכנסת כ"תוספת" בשלב מאוחר יותר, לא כחלק אינטגרלי מההתחלה.

---

## סיכום סדר העדיפויות

1. ליבה טכנית שעונה טוב ומזהה חוסרים (שלב 1)
2. לולאת משוב עם פקידת הקבלה, כולל שכבת כתיבה אוטומטית (שלב 2)
3. כלי פיקוח קלים לך ולבעל המלון (שלב 3)
4. הרחבות עסקיות — רק אחרי שהערך הבסיסי הוכח (שלב 4)
