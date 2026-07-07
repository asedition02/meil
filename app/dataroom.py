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


def save_upload(folder: str, filename: str, content: bytes) -> dict:
    """Kullanıcının yüklediği dosyayı dataroom'a kaydeder."""
    parts = [_safe_name(p) for p in (folder or "").split("/") if p.strip()]
    target_dir = config.DATAROOM_DIR.joinpath(*parts) if parts else config.DATAROOM_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    name = _safe_name(filename)
    target = target_dir / name
    counter = 1
    while target.exists():
        stem, suffix = os.path.splitext(name)
        target = target_dir / f"{stem}_{counter}{suffix}"
        counter += 1
    target.write_bytes(content)
    return {
        "filename": target.name,
        "path": str(target.relative_to(config.DATAROOM_DIR)),
        "size": len(content),
    }


def delete_file(rel_path: str):
    """Dosyayı siler; boşalan klasörleri temizler."""
    target = resolve_file(rel_path)
    root = config.DATAROOM_DIR.resolve()
    target.unlink()
    parent = target.parent
    while parent != root and parent.is_dir() and not any(parent.iterdir()):
        parent.rmdir()
        parent = parent.parent


def list_folders() -> list[str]:
    """Dataroom'daki tüm klasörleri (boşlar dahil) listeler."""
    folders = []
    for path in sorted(config.DATAROOM_DIR.rglob("*")):
        if path.is_dir():
            folders.append(str(path.relative_to(config.DATAROOM_DIR)))
    return folders


def _safe_folder(folder: str) -> Path:
    parts = [_safe_name(p) for p in (folder or "").split("/") if p.strip()]
    return config.DATAROOM_DIR.joinpath(*parts) if parts else config.DATAROOM_DIR


def create_folder(folder: str) -> str:
    target = _safe_folder(folder)
    target.mkdir(parents=True, exist_ok=True)
    return str(target.relative_to(config.DATAROOM_DIR)) if target != config.DATAROOM_DIR else ""


def move_file(rel_path: str, folder: str) -> str:
    """Dosyayı başka klasöre taşır; yeni göreli yolu döner."""
    source = resolve_file(rel_path)
    target_dir = _safe_folder(folder)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    counter = 1
    while target.exists():
        stem, suffix = os.path.splitext(source.name)
        target = target_dir / f"{stem}_{counter}{suffix}"
        counter += 1
    source.rename(target)
    # boşalan eski klasörleri temizle
    root = config.DATAROOM_DIR.resolve()
    parent = source.parent
    while parent != root and parent.is_dir() and not any(parent.iterdir()):
        parent.rmdir()
        parent = parent.parent
    return str(target.relative_to(config.DATAROOM_DIR))
