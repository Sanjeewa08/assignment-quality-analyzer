from pathlib import Path

from werkzeug.utils import secure_filename

from .base import ExtractionError
from .docx import DocxExtractor
from .image import ImageExtractor
from .pdf import PdfExtractor
from .slides import LegacyPowerPointExtractor, PowerPointExtractor
from .text import TextExtractor


class ExtractorFactory:
    _extractors = (TextExtractor, DocxExtractor, PdfExtractor, PowerPointExtractor, LegacyPowerPointExtractor, ImageExtractor)
    _by_extension = {
        extension: extractor
        for extractor in _extractors
        for extension in extractor.extensions
    }
    supported_extensions = frozenset(_by_extension)

    @classmethod
    def for_path(cls, path):
        safe_name = secure_filename(Path(path).name)
        extension = Path(safe_name).suffix.lower()
        extractor = cls._by_extension.get(extension)
        if extractor is None:
            supported = ", ".join(sorted(cls.supported_extensions))
            raise ExtractionError(f"Unsupported file type. Supported formats: {supported}.")
        return extractor()
