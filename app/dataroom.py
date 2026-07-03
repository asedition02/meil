"""Mail eklerinin kaydedildiği dataroom."""
import os
import re
from pathlib import Path

from . import config


def _safe_name(name: str) -> str:
    name = os.path.basename(name)
    name = re.sub(r"[^\w.\-() ğüşıöçĞÜŞİÖÇ]", "_", name)
    return name.strip() or "adsiz"


def save_attachments(sender_email: str, date_iso: str,
                     attachments: list[tuple[str, bytes]]) -> list[dict]:
    """Ekleri dataroom/GÖNDEREN/TARİH/ altına kaydeder, metadata döner."""
    saved = []
    if not attachments:
        return saved
    day = (date_iso or "")[:10] or "tarihsiz"
    folder = config.DATAROOM_DIR / _safe_name(sender_email or "bilinmeyen") / day
    folder.mkdir(parents=True, exist_ok=True)
    for filename, payload in attachments:
        name = _safe_name(filename)
        target = folder / name
        # aynı isimde dosya varsa numaralandır
        counter = 1
        while target.exists():
            stem, suffix = os.path.splitext(name)
            target = folder / f"{stem}_{counter}{suffix}"
            counter += 1
        target.write_bytes(payload)
        saved.append(
            {
                "filename": target.name,
                "path": str(target.relative_to(config.DATAROOM_DIR)),
                "size": len(payload),
            }
        )
    return saved


def list_files() -> list[dict]:
    """Dataroom'daki tüm dosyaları listeler."""
    files = []
    for path in sorted(config.DATAROOM_DIR.rglob("*")):
        if path.is_file():
            rel = path.relative_to(config.DATAROOM_DIR)
            files.append(
                {
                    "path": str(rel),
                    "filename": path.name,
                    "folder": str(rel.parent),
                    "size": path.stat().st_size,
                    "modified": path.stat().st_mtime,
                }
            )
    files.sort(key=lambda f: f["modified"], reverse=True)
    return files


def resolve_file(rel_path: str) -> Path:
    """Yol doğrulaması: dataroom dışına çıkışı engeller."""
    target = (config.DATAROOM_DIR / rel_path).resolve()
    root = config.DATAROOM_DIR.resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise FileNotFoundError(rel_path)
    return target
