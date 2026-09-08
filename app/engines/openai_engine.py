import json

from openai import OpenAI

from app.config import settings
from app.engines.base import AIEngine, EngineError, EngineResponse, compose_system

# Structured output schema — guarantees `text` and `found_in_kb` always come
# back typed, regardless of prompt content. This is the Responses API shape
# (nested under the `text` request param), not the older Chat Completions
# `response_format` shape.
_TEXT_FORMAT = {
    "format": {
        "type": "json_schema",
        "name": "concierge_reply",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The reply to the guest, in the guest's language.",
                },
                "found_in_kb": {
                    "type": "boolean",
                    "description": (
                        "True only if information from the provided knowledge base "
                        "was actually used in the reply."
                    ),
                },
            },
            "required": ["text", "found_in_kb"],
            "additionalProperties": False,
        },
    },
}

# The model decides per-question whether it needs current web info (e.g.
# "what events are on this week?") — unlike Chat Completions' search-preview
# models, which force a search on every single call. Costs nothing extra on
# questions the model answers without searching (KB hits, general chat).
# This is why OpenAIAdapter uses the Responses API instead of Chat
# Completions: Chat Completions has no equivalent model-decides-when option.
_TOOLS = [{"type": "web_search"}]


class OpenAIAdapter(AIEngine):
    provider_name = "openai"

    def __init__(self, api_key: str, model: str | None = None):
        self._client = OpenAI(api_key=api_key)
        self._model = model or settings.openai_model

    def ask(self, system_prompt: str, context: str, question: str) -> EngineResponse:
        response = self._client.responses.create(
            model=self._model,
            input=[
                {"role": "system", "content": compose_system(system_prompt, context)},
                {"role": "user", "content": question},
            ],
            tools=_TOOLS,
            text=_TEXT_FORMAT,
        )

        # response.output is a list that may include web_search_call items
        # (when the model searched) alongside the final message — find the
        # message explicitly rather than assuming a fixed position/index.
        message = next((item for item in response.output if item.type == "message"), None)
        content = message.content[0] if message and message.content else None

        if content is None:
            raise EngineError("OpenAI returned no message output")
        if content.type == "refusal":
            raise EngineError(f"OpenAI refused to answer: {content.refusal}")

        try:
            data = json.loads(content.text)
        except json.JSONDecodeError as exc:
            raise EngineError("OpenAI response was not valid JSON") from exc

        return EngineResponse(
            text=str(data["text"]),
            found_in_kb=bool(data["found_in_kb"]),
            raw_provider_response=response.model_dump(),
        )