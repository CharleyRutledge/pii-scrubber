"""OCR support for detecting PII baked into images (scanned IDs, photos,
screenshots) rather than present as real text. Optional — requires the
`ocr` extra (pytesseract + Pillow) plus a system Tesseract OCR install,
which pip cannot provide on its own.
"""

import shutil
from functools import lru_cache
from io import BytesIO

# Common Windows install location when Tesseract isn't on PATH.
_WINDOWS_FALLBACK_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


@lru_cache(maxsize=1)
def _configure_tesseract():
    try:
        import pytesseract
    except ImportError as exc:
        raise RuntimeError(
            "Image OCR requires pytesseract + Pillow. Install with: "
            "pip install pii-scrubber[ocr]"
        ) from exc

    if shutil.which("tesseract") is None:
        for candidate in _WINDOWS_FALLBACK_PATHS:
            import os

            if os.path.isfile(candidate):
                pytesseract.pytesseract.tesseract_cmd = candidate
                break
        else:
            raise RuntimeError(
                "Tesseract OCR engine not found on PATH. Install it "
                "(e.g. `winget install --id UB-Mannheim.TesseractOCR`) "
                "or set pytesseract.pytesseract.tesseract_cmd manually."
            )

    return pytesseract


def ocr_image_bytes(image_bytes: bytes) -> str:
    """Run OCR over raw image bytes and return any text found."""
    pytesseract = _configure_tesseract()
    from PIL import Image

    with Image.open(BytesIO(image_bytes)) as img:
        return pytesseract.image_to_string(img)
