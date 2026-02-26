import re
from pathlib import Path

from docx import Document
from pypdf import PdfReader


def normalize_text(text: str) -> str:
    cleaned = text.replace("\u00a0", " ").replace("\u200b", "")
    cleaned = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", cleaned)
    cleaned = re.sub(r"\s*\n\s*", "\n", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def extract_text(storage_key: str, content_type: str) -> str:
    path = Path(storage_key)
    if not path.exists():
        raise FileNotFoundError(storage_key)

    normalized_type = (content_type or "").lower()
    suffix = path.suffix.lower()

    if normalized_type == "text/plain" or suffix == ".txt":
        text = normalize_text(path.read_text(encoding="utf-8", errors="ignore"))
        if text:
            return text
        raise ValueError("TXT file has no readable text")

    if normalized_type == "application/pdf" or suffix == ".pdf":
        reader = PdfReader(str(path))
        pages = [normalize_text(page.extract_text() or "") for page in reader.pages]
        text = normalize_text("\n\n".join(part for part in pages if part))
        if text.strip():
            return text.strip()
        raise ValueError("PDF file has no extractable text")

    if (
        normalized_type
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        or suffix == ".docx"
    ):
        doc = Document(str(path))
        paragraphs = [normalize_text(p.text) for p in doc.paragraphs if p.text and p.text.strip()]
        text = normalize_text("\n".join(paragraphs))
        if text.strip():
            return text.strip()
        raise ValueError("DOCX file has no extractable text")

    raise ValueError(f"Unsupported content type for parser: {content_type}")


def split_into_chunks(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    text = normalize_text(text)
    if not text.strip():
        return []

    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= chunk_size:
            current = f"{current} {sentence}".strip()
            continue

        if current:
            chunks.append(current)
            if overlap > 0 and len(current) > overlap:
                current = current[-overlap:]
            else:
                current = ""

        current = f"{current} {sentence}".strip()

    if current:
        chunks.append(current)

    return [c for c in chunks if c.strip()]