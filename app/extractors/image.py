from pathlib import Path
import os

from .base import DocumentExtractor, ExtractedDocument, ExtractionError


class ImageExtractor(DocumentExtractor):
    extensions = frozenset({".jpg", ".jpeg", ".png"})

    def extract(self, path: Path) -> ExtractedDocument:
        try:
            from PIL import Image
            import pytesseract

            if os.environ.get("TESSERACT_CMD"):
                pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                text = pytesseract.image_to_string(image)
        except ImportError as exc:
            raise ExtractionError("Image OCR requires Pillow and Tesseract. Install them to analyze images.") from exc
        except OSError as exc:
            raise ExtractionError("The image is corrupted or could not be read.") from exc
        except Exception as exc:
            raise ExtractionError("Tesseract OCR could not process this image.") from exc
        if not text.strip():
            raise ExtractionError("OCR found no readable text in this image.")
        return ExtractedDocument(text)
