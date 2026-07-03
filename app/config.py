"""Uygulama yapılandırması — ortam değişkenlerinden okunur (.env desteklenir)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# E-posta hesabı (Gmail için uygulama şifresi kullanın: https://myaccount.google.com/apppasswords)
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")

IMAP_HOST = os.environ.get("IMAP_HOST", "imap.gmail.com")
IMAP_PORT = int(os.environ.get("IMAP_PORT", "993"))
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))

# Claude API
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-8")

# Depolama
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
DATAROOM_DIR = Path(os.environ.get("DATAROOM_DIR", DATA_DIR / "dataroom"))
DB_PATH = Path(os.environ.get("DB_PATH", DATA_DIR / "meil.db"))

# Her eşitlemede en fazla kaç yeni mail işlensin
SYNC_LIMIT = int(os.environ.get("SYNC_LIMIT", "25"))

# Kullanıcının imzası / yanıtlarda kullanılacak isim
USER_NAME = os.environ.get("USER_NAME", "")

DATA_DIR.mkdir(parents=True, exist_ok=True)
DATAROOM_DIR.mkdir(parents=True, exist_ok=True)
