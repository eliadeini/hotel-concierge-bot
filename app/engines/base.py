"""Uniform interface every AI provider adapter implements.

Business logic (the /chat endpoint) only ever talks to AIEngine.ask() —
never to a provider SDK directly.
"""

from abc import ABC, abstractmethod

from pydantic import BaseModel


class EngineError(RuntimeError):
    pass


class EngineResponse(BaseModel):
    text: str
    found_in_kb: bool
    # Internal/debug only — must never be returned to API clients.
    raw_provider_response: dict | None = None


class AIEngine(ABC):
    # Overridden by each adapter; used for anonymous logging.
    provider_name: str = "unknown"

    @abstractmethod
    def ask(self, system_prompt: str, context: str, question: str) -> EngineResponse:
        ...


def compose_system(system_prompt: str, context: str) -> str:
    """Combine the fixed system prompt with the knowledge-base context.

    Shared by all adapters so every provider sees an identical prompt.
    """
    if not context.strip():
        return (
            f"{system_prompt}\n\n<knowledge_base>\n(no local knowledge available "
            f"for this region)\n</knowledge_base>"
        )
    return f"{system_prompt}\n\n<knowledge_base>\n{context}\n</knowledge_base>"
