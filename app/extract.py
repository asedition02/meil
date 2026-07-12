"""Dataroom dosyalarından metin çıkarma (içerik araması ve AI analizi için)."""
import logging
import re
import zipfile
from pathlib import Path

log = logging.getLogger("meil")

MAX_CHARS = 60_000  # arama dizini ve AI girişi için üst sınır

TEXT_EXTS = {".txt", ".md", ".csv", ".log", ".json", ".xml", ".html", ".htm"}


def _strip_xml(xml: str) -> str:
    # Office XML'inde paragraf/satır sonlarını koru, kalan etiketleri at
    xml = re.sub(r"</w:p>|</a:p>|<w:br[^>]*/>|<text:line-break[^>]*/>", "\n", xml)
    text = re.sub(r"<[^>]+>", " ", xml)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _from_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    parts = []
    total = 0
    for page in reader.pages:
        t = page.extract_text() or ""
        parts.append(t)
        total += len(t)
        if total > MAX_CHARS:
            break
    return "\n".join(parts)


def _from_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    return _strip_xml(xml)


def _from_xlsx(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if n == "xl/sharedStrings.xml"]
        if not names:
            return ""
        xml = z.read(names[0]).decode("utf-8", errors="replace")
    return _strip_xml(xml)


def _from_pptx(path: Path) -> str:
    parts = []
    with zipfile.ZipFile(path) as z:
        slides = sorted(n for n in z.namelist()
                        if n.startswith("ppt/slides/slide") and n.endswith(".xml"))
        for name in slides:
            xml = z.read(name).decode("utf-8", errors="replace")
            parts.append(_strip_xml(xml))
    return "\n\n".join(parts)


def extract_text(path: Path) -> str:
    """Dosyadan düz metin çıkarır; desteklenmeyen/bozuk dosyada boş string döner."""
    ext = path.suffix.lower()
    try:
        if ext == ".pdf":
            text = _from_pdf(path)
        elif ext == ".docx":
            text = _from_docx(path)
        elif ext == ".xlsx":
            text = _from_xlsx(path)
        elif ext == ".pptx":
            text = _from_pptx(path)
        elif ext in TEXT_EXTS:
            text = path.read_text(encoding="utf-8", errors="replace")
        else:
            return ""
    except Exception as e:
        log.warning("Metin çıkarılamadı %s: %s", path.name, e)
        return ""
    return text.strip()[:MAX_CHARS]
