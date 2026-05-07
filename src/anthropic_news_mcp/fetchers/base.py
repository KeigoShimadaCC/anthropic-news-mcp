from abc import ABC, abstractmethod

from ..models import NewsItem


class Fetcher(ABC):
    """Each source implements this. Stateless: no instance state between calls."""

    source_key: str  # Set as a class variable in concrete subclasses

    @abstractmethod
    async def fetch(self) -> list[NewsItem]:
        """Fetch fresh items.

        Raises on transport-level failures. Returns [] on empty source.
        Implementations MUST set NewsItem.source_key to self.source_key.
        Implementations MUST NOT do their own caching.
        """
        ...
