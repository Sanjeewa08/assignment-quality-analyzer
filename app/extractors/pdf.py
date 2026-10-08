from pathlib import Path
import os

import pdfplumber

from .base import DocumentExtractor, ExtractedDocument, ExtractionError


class PdfExtractor(DocumentExtractor):
    extensions = frozenset({".pdf"})

    def extract(self, path: Path) -> ExtractedDocument:
        try:
            with pdfplumber.open(path) as pdf:
                pages = [page.extract_text() or "" for page in pdf.pages]
        except Exception as exc:
            raise ExtractionError("The PDF is corrupted or could not be read.") from exc

        text = "\n\n".join(page for page in pages if page.strip())
        if text.strip():
            return ExtractedDocument(text)
        return self._ocr(path)

    @staticmethod
    def _ocr(path: Path) -> ExtractedDocument:
        try:
            from pdf2image import convert_from_path
            import pytesseract

            if os.environ.get("TESSERACT_CMD"):
                pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]
            images = convert_from_path(path, timeout=90)
            text = "\n\n".join(pytesseract.image_to_string(image) for image in images)
        except (ImportError, OSError, RuntimeError) as exc:
            raise ExtractionError(
                "No text was found in this PDF. Scanned PDFs need Poppler and Tesseract OCR installed."
            ) from exc
        except Exception as exc:
            raise ExtractionError("OCR could not read this scanned PDF. Check the OCR installation and file.") from exc
        if not text.strip():
            raise ExtractionError("OCR found no readable text in this scanned PDF.")
        return ExtractedDocument(text)
