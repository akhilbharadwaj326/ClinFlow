from PIL import Image
import pytesseract


def extract_text_from_image(file_path: str) -> str:
    """
    Runs Tesseract OCR on an image file and returns the extracted text.
    Raises an exception if the file cannot be processed.

    Requirements:
    - Tesseract must be installed on the machine.
    - Windows: set the path below if Tesseract is not in PATH.
    """
    # Uncomment on Windows if Tesseract is not in system PATH:
    # pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    try:
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as exc:
        raise RuntimeError(f"OCR failed for file {file_path}: {exc}") from exc


def extract_text_from_manual(raw_text: str) -> str:
    """Passthrough for manually entered text."""
    return raw_text.strip()
