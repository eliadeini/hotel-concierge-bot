# `app/engines/` — AI provider abstraction

## Why this exists
Each hotel can pick its own AI provider (`hotel_settings.ai_engine`), and
that choice needs to be a config change, not a code change. So business
logic (`app/api/chat.py`) never talks to an OpenAI or Anthropic SDK
directly — it only calls `AIEngine.ask(...)`. Swapping or adding a
provider means writing one new adapter here; nothing outside this folder
changes.

## Layout
- **`base.py`** — the `AIEngine` interface (`ask()`), the shared
  `EngineResponse` model (`text`, `found_in_kb`, `raw_provider_response`),
  and `compose_system()`, which merges the fixed system prompt with the
  knowledge-base context identically for every provider.
- **`openai_engine.py`** — `OpenAIAdapter`. Uses OpenAI's `json_schema`
  structured output to force `text`/`found_in_kb` back in a fixed shape.
- **`claude_engine.py`** — `ClaudeAdapter`. Uses Claude's forced tool use
  (`tool_choice`) to get the same structural guarantee.
- **`factory.py`** — `get_engine(hotel_id, db)`. Looks up the hotel's
  settings row, decrypts its API key, and returns the matching adapter.
  This is the *only* place that decides which adapter to instantiate.

## Adding a new provider
1. Create `<provider>_engine.py` with a class implementing `AIEngine.ask()`
   and returning `EngineResponse`.
2. Add the new value to `AIEngineType` in `app/models/hotel_settings.py`.
3. Wire it into `factory.get_engine()`.

`raw_provider_response` is for debugging only and must never reach an API
client — see the note in `base.py`.