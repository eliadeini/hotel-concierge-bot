"""Structured-output normalization tests — provider SDK clients are mocked."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.engines.base import EngineError, compose_system
from app.engines.claude_engine import ClaudeAdapter
from app.engines.openai_engine import OpenAIAdapter


def make_openai_adapter(content: str | None, response_id: str = "resp_1"):
    adapter = OpenAIAdapter(api_key="sk-fake")
    if content is None:
        output = []  # no message item — simulates an empty/incomplete response
    else:
        output = [
            SimpleNamespace(
                type="message",
                content=[SimpleNamespace(type="output_text", text=content)],
            )
        ]
    response = SimpleNamespace(
        id=response_id, output=output, model_dump=lambda: {"provider": "openai-raw"}
    )
    adapter._client = MagicMock()
    adapter._client.responses.create.return_value = response
    return adapter


def make_claude_adapter(blocks: list):
    adapter = ClaudeAdapter(api_key="sk-ant-fake")
    response = SimpleNamespace(
        content=blocks, model_dump=lambda: {"provider": "claude-raw"}
    )
    adapter._client = MagicMock()
    adapter._client.messages.create.return_value = response
    return adapter


def test_openai_normalizes_structured_output():
    adapter = make_openai_adapter(json.dumps({"text": "hello", "found_in_kb": True}))
    result = adapter.ask("sys", "ctx", "q")
    assert result.text == "hello"
    assert result.found_in_kb is True
    assert result.raw_provider_response == {"provider": "openai-raw"}


def test_openai_invalid_json_raises():
    adapter = make_openai_adapter("not json at all")
    with pytest.raises(EngineError):
        adapter.ask("sys", "ctx", "q")


def test_openai_empty_response_raises():
    adapter = make_openai_adapter(None)
    with pytest.raises(EngineError):
        adapter.ask("sys", "ctx", "q")


def test_openai_refusal_raises():
    adapter = OpenAIAdapter(api_key="sk-fake")
    response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="message",
                content=[SimpleNamespace(type="refusal", refusal="can't help with that")],
            )
        ],
        model_dump=lambda: {"provider": "openai-raw"},
    )
    adapter._client = MagicMock()
    adapter._client.responses.create.return_value = response
    with pytest.raises(EngineError):
        adapter.ask("sys", "ctx", "q")


def test_openai_includes_web_search_tool():
    """The model decides per-question whether to search — this just confirms
    the tool is actually offered on every call, not that search happened."""
    adapter = make_openai_adapter(json.dumps({"text": "hi", "found_in_kb": False}))
    adapter.ask("sys", "ctx", "q")
    _, kwargs = adapter._client.responses.create.call_args
    assert kwargs["tools"] == [{"type": "web_search"}]


def test_openai_retries_with_search_nudge_when_not_found_and_not_searched():
    adapter = OpenAIAdapter(api_key="sk-fake")
    first = SimpleNamespace(
        id="resp_1",
        output=[
            SimpleNamespace(
                type="message",
                content=[
                    SimpleNamespace(
                        type="output_text",
                        text=json.dumps({"text": "no idea", "found_in_kb": False}),
                    )
                ],
            )
        ],
        model_dump=lambda: {"provider": "openai-raw-1"},
    )
    second = SimpleNamespace(
        id="resp_2",
        output=[
            SimpleNamespace(type="web_search_call"),
            SimpleNamespace(
                type="message",
                content=[
                    SimpleNamespace(
                        type="output_text",
                        text=json.dumps({"text": "found it", "found_in_kb": False}),
                    )
                ],
            ),
        ],
        model_dump=lambda: {"provider": "openai-raw-2"},
    )
    adapter._client = MagicMock()
    adapter._client.responses.create.side_effect = [first, second]

    result = adapter.ask("sys", "ctx", "q")

    assert result.text == "found it"
    assert adapter._client.responses.create.call_count == 2
    _, second_kwargs = adapter._client.responses.create.call_args
    assert second_kwargs["previous_response_id"] == "resp_1"


def test_openai_does_not_retry_when_search_already_attempted():
    adapter = OpenAIAdapter(api_key="sk-fake")
    response = SimpleNamespace(
        id="resp_1",
        output=[
            SimpleNamespace(type="web_search_call"),
            SimpleNamespace(
                type="message",
                content=[
                    SimpleNamespace(
                        type="output_text",
                        text=json.dumps({"text": "searched already", "found_in_kb": False}),
                    )
                ],
            ),
        ],
        model_dump=lambda: {"provider": "openai-raw"},
    )
    adapter._client = MagicMock()
    adapter._client.responses.create.return_value = response

    result = adapter.ask("sys", "ctx", "q")

    assert result.text == "searched already"
    assert adapter._client.responses.create.call_count == 1


def test_claude_normalizes_tool_use():
    blocks = [
        SimpleNamespace(type="text", text="preamble"),
        SimpleNamespace(
            type="tool_use", input={"text": "shalom", "found_in_kb": False}
        ),
    ]
    adapter = make_claude_adapter(blocks)
    result = adapter.ask("sys", "ctx", "q")
    assert result.text == "shalom"
    assert result.found_in_kb is False
    assert result.raw_provider_response == {"provider": "claude-raw"}


def test_claude_missing_tool_use_raises():
    adapter = make_claude_adapter([SimpleNamespace(type="text", text="no tool call")])
    with pytest.raises(EngineError):
        adapter.ask("sys", "ctx", "q")


def test_both_adapters_return_identical_shape():
    openai_result = make_openai_adapter(
        json.dumps({"text": "same", "found_in_kb": True})
    ).ask("s", "c", "q")
    claude_result = make_claude_adapter(
        [SimpleNamespace(type="tool_use", input={"text": "same", "found_in_kb": True})]
    ).ask("s", "c", "q")
    assert openai_result.model_dump(exclude={"raw_provider_response"}) == (
        claude_result.model_dump(exclude={"raw_provider_response"})
    )


def test_compose_system_includes_context():
    combined = compose_system("PROMPT", "some local knowledge")
    assert combined.startswith("PROMPT")
    assert "some local knowledge" in combined


def test_compose_system_handles_empty_context():
    combined = compose_system("PROMPT", "   ")
    assert "no local knowledge available" in combined
