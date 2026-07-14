"""Uygulama girişi: PIN/parola + oturum çerezi.

- PIN, PBKDF2-SHA256 (200k tur, rastgele tuz) ile özetlenip settings
  tablosunda saklanır; düz metin hiçbir yerde tutulmaz.
- Başarılı girişte rastgele bir oturum jetonu üretilir, sessions tablosuna
  yazılır ve HttpOnly çerezle tarayıcıya verilir (30 gün, kayan süre).
- Kaba kuvvete karşı: 5 hatalı denemeden sonra 60 saniye kilit (IP başına).
"""
import hashlib
import secrets
import time

from . import database

SESSION_COOKIE = "meil_session"
SESSION_DAYS = 30
PBKDF2_ITERS = 200_000
MAX_ATTEMPTS = 5
LOCK_SECONDS = 60

# IP → [hatalı deneme zamanları]
_failed: dict[str, list[float]] = {}


def _hash_pin(pin: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, PBKDF2_ITERS).hex()


def pin_is_set() -> bool:
    return database.get_setting("pin_hash") is not None


def set_pin(pin: str):
    salt = secrets.token_bytes(16)
    database.set_setting("pin_hash", salt.hex() + "$" + _hash_pin(pin, salt))


def verify_pin(pin: str) -> bool:
    stored = database.get_setting("pin_hash")
    if not stored:
        return False
    salt_hex, _, expected = stored.partition("$")
    actual = _hash_pin(pin, bytes.fromhex(salt_hex))
    return secrets.compare_digest(actual, expected)


def is_locked(ip: str) -> int:
    """Kilitliyse kalan saniyeyi, değilse 0 döner."""
    now = time.time()
    attempts = [t for t in _failed.get(ip, []) if now - t < LOCK_SECONDS]
    _failed[ip] = attempts
    if len(attempts) >= MAX_ATTEMPTS:
        return int(LOCK_SECONDS - (now - attempts[0])) + 1
    return 0


def record_failure(ip: str):
    _failed.setdefault(ip, []).append(time.time())


def clear_failures(ip: str):
    _failed.pop(ip, None)


def create_session() -> str:
    token = secrets.token_urlsafe(32)
    database.create_session(token, SESSION_DAYS)
    return token


def session_valid(token: str | None) -> bool:
    if not token:
        return False
    return database.touch_session(token, SESSION_DAYS)


def destroy_session(token: str | None):
    if token:
        database.delete_session(token)
