from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


class ExtractionError(ValueError):
    """A user-facing error raised when an uploaded document cannot be extracted."""


@dataclass
class ExtractedDocument:
    text: str
    formatting: dict = field(default_factory=dict)


class DocumentExtractor(ABC):
    extensions = frozenset()

    @abstractmethod
    def extract(self, path: Path) -> ExtractedDocument:
        """Extract readable content from a validated file."""
