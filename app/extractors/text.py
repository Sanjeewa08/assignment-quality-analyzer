from pathlib import Path

from .base import DocumentExtractor, ExtractedDocument, ExtractionError


class TextExtractor(DocumentExtractor):
    extensions = frozenset({".txt"})

    def extract(self, path: Path) -> ExtractedDocument:
        try:
            return ExtractedDocument(path.read_text(encoding="utf-8-sig"))
        except (UnicodeError, OSError) as exc:
            raise ExtractionError("This text file is not valid UTF-8 or could not be read.") from exc
