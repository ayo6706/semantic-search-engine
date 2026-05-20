from abc import ABC, abstractmethod

from app.schemas.search import ScoredChunk


class BaseFuser(ABC):
    """Abstract base class for score fusion strategies."""

    @abstractmethod
    def fuse(self, result_sets: list[list[ScoredChunk]]) -> list[ScoredChunk]:
        """Fuse multiple sets of retrieved chunks into a single ranked list.

        Args:
            result_sets: A list containing lists of ScoredChunk objects from
                different retrievers.

        Returns:
            A single, fused list of ScoredChunk objects.
        """
        pass
