"""Uygulama yapılandırması — ortam değişkenlerinden okunur (.env desteklenir)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# İlk açılışta otomatik hesap oluşturmak için (isteğe bağlı — hesaplar
# artık arayüzden de eklenebiliyor). Gmail için uygulama şifresi kullanın:
# https://myaccount.google.com/apppasswords
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "").strip()
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "").strip()
IMAP_HOST = os.environ.get("IMAP_HOST", "imap.gmail.com")
IMAP_PORT = int(os.environ.get("IMAP_PORT", "993"))
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_SECURITY = os.environ.get("SMTP_SECURITY", "ssl")

# Claude API
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-8")

# Depolama
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
DATAROOM_DIR = Path(os.environ.get("DATAROOM_DIR", DATA_DIR / "dataroom"))
DB_PATH = Path(os.environ.get("DB_PATH", DATA_DIR / "meil.db"))

# Her eşitlemede hesap başına en fazla kaç yeni mail işlensin
SYNC_LIMIT = int(os.environ.get("SYNC_LIMIT", "25"))

# Kullanıcının imzası / yanıtlarda kullanılacak isim
USER_NAME = os.environ.get("USER_NAME", "")

# Microsoft 365 / Outlook OAuth (XOAUTH2) — Entra ID uygulama kaydı gerekir.
# Microsoft, Nisan 2026'da IMAP/SMTP için şifreyle girişi tamamen kapattı;
# Outlook hesapları artık yalnızca OAuth ile bağlanabilir. Bkz. README.
# Varsayılan: "Meil" uygulama kaydı (public client — gizli anahtar içermez,
# cihaz kodu akışında kimlik doğrulamayı her zaman Microsoft'un kendisi yapar).
MS_CLIENT_ID = os.environ.get("MS_CLIENT_ID", "").strip() or "2fae9a13-5d84-42f9-bf8b-ff4085924a42"
MS_TENANT = os.environ.get("MS_TENANT", "common").strip() or "common"

# Üretim modu: TLS/HTTPS, secure cookies, HSTS, vb. — Caddy gibi ters proxy
# arkasında VPS'ye kurulum için True olmalıdır. Yerel geliştirme için False.
# production = True → set_cookie'de secure=True, SameSite=Strict, HSTS başlığı ekler.
PRODUCTION = os.environ.get("PRODUCTION", "").lower() in ("true", "1", "yes")

DATA_DIR.mkdir(parents=True, exist_ok=True)
DATAROOM_DIR.mkdir(parents=True, exist_ok=True)
