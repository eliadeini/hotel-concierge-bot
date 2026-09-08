"""Uniform interface for knowledge retrieval.

The /chat endpoint only ever calls KnowledgeSource.get_context() — never the
filesystem directly. A future PostgresSource is a swap of implementation, not
a refactor (the interface exists now; the implementation is deliberately NOT
built in phase 1).
"""

from abc import ABC, abstractmethod


class KnowledgeSource(ABC):
    @abstractmethod
    def get_context(
        self, hotel_id: str, region: str, category: str | None = None
    ) -> str:
        """Return the concatenated knowledge entries for a region as one string.

        An empty string means no local knowledge is available.
        """
        ...
