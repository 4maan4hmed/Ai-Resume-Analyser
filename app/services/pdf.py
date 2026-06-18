from io import BytesIO
from pypdf import PdfReader


def extract_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    pages = [p.extract_text().strip() for p in reader.pages if p.extract_text()]
    text = "\n".join(pages).strip()
    if not text:
        raise ValueError("Could not extract text from PDF")
    return text
