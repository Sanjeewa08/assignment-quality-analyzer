from pathlib import Path
from tempfile import TemporaryDirectory

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from .base import ExtractedDocument, ExtractionError
from .factory import ExtractorFactory


def extract_document(path):
    return ExtractorFactory.for_path(path).extract(Path(path))


def extract_text(file_storage):
    """Compatibility helper for callers that still use Werkzeug FileStorage."""
    filename = secure_filename(file_storage.filename or "")
    if not filename:
        raise ExtractionError("Please choose a file to analyze.")
    with TemporaryDirectory(prefix="aqa-") as directory:
        path = Path(directory) / filename
        file_storage.save(path)
        return extract_document(path).text


__all__ = ["ExtractedDocument", "ExtractionError", "ExtractorFactory", "extract_document", "extract_text"]
