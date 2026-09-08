import anthropic

from app.config import settings
from app.engines.base import AIEngine, EngineError, EngineResponse, compose_system

# Forced tool use gives the same guaranteed structured output as OpenAI's
# json_schema response format.
_REPLY_TOOL = {
    "name": "concierge_reply",
    "description": "Deliver the final reply to the hotel guest.",
    "input_schema": {
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
}


class ClaudeAdapter(AIEngine):
    provider_name = "claude"

    def __init__(self, api_key: str, model: str | None = None):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model or settings.claude_model

    def ask(self, system_prompt: str, context: str, question: str) -> EngineResponse:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=compose_system(system_prompt, context),
            messages=[{"role": "user", "content": question}],
            tools=[_REPLY_TOOL],
            tool_choice={"type": "tool", "name": "concierge_reply"},
        )
        data = next(
            (block.input for block in response.content if block.type == "tool_use"),
            None,
        )
        if data is None:
            raise EngineError("Claude did not return the structured reply tool call")
        return EngineResponse(
            text=str(data["text"]),
            found_in_kb=bool(data["found_in_kb"]),
            raw_provider_response=response.model_dump(),
        )
