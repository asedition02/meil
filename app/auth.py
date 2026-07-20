"""Uygulama girişi: parola + oturum çerezi.

Güvenlik notları:
- Parola, PBKDF2-SHA256 (600k tur, rastgele 16 baytlık tuz) ile özetlenir ve
  settings tablosunda `salt$iters$hash` biçiminde saklanır; düz metin hiçbir
  yerde tutulmaz. Eski (200k tur) kayıtlar ilk başarılı girişte otomatik olarak
  güncel tur sayısıyla yeniden özetlenir.
- Karşılaştırma sabit zamanlıdır (secrets.compare_digest) — zamanlama sızıntısı yok.
- Başarılı girişte rastgele yeni bir oturum jetonu üretilir (oturum sabitleme
  saldırısına karşı jeton yenileme), sessions tablosuna yazılır ve HttpOnly
  çerezle verilir (30 gün, kayan süre).
- Kaba kuvvete karşı IP başına kademeli kilit: 5 hata → 60 sn, 8 hata → 5 dk,
  12+ hata → 30 dk. Süre son denemeye göre işler (kilitliyken deneme süreyi uzatır).
"""
import hashlib
import json
import math
import secrets
import time

from . import crypto, database, totp

SESSION_COOKIE = "meil_session"
SESSION_DAYS = 30
PBKDF2_ITERS = 600_000          # OWASP 2023 önerisi (PBKDF2-SHA256)
MIN_PASSWORD_LEN = 8

# Kaba kuvvet: pencere içinde biriken hatalar
_FAIL_WINDOW = 900              # 15 dk
_LOCK_TIERS = ((12, 1800), (8, 300), (5, 60))   # (hata sayısı, kilit saniyesi)

# IP → [hatalı deneme zaman damgaları]
_failed: dict[str, list[float]] = {}


# ---- Parola özeti ----

def _hash(pw: str, salt: bytes, iters: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, iters).hex()


def password_problem(pw: str) -> str | None:
    """Parola yeterince güçlü değilse Türkçe hata mesajı, güçlüyse None döner."""
    pw = pw or ""
    if len(pw) < MIN_PASSWORD_LEN:
        return f"Parola en az {MIN_PASSWORD_LEN} karakter olmalı"
    if len(set(pw)) < 4:
        return "Parola çok basit — daha çeşitli karakterler kullanın"
    low = pw.lower()
    if low in {"password", "parola", "12345678", "123456789", "1234567890",
               "qwerty123", "meil1234", "11111111", "00000000"}:
        return "Bu parola çok yaygın — başka bir parola seçin"
    # tamamen ardışık / tek karakter
    if len(set(pw)) == 1:
        return "Parola çok basit — daha çeşitli karakterler kullanın"
    return None


def pin_is_set() -> bool:
    return database.get_setting("pin_hash") is not None


def set_pin(pw: str) -> None:
    """Parolayı güncel tur sayısıyla özetleyip saklar."""
    salt = secrets.token_bytes(16)
    database.set_setting("pin_hash", f"{salt.hex()}${PBKDF2_ITERS}${_hash(pw, salt, PBKDF2_ITERS)}")


def verify_pin(pw: str) -> bool:
    stored = database.get_setting("pin_hash")
    if not stored:
        return False
    parts = stored.split("$")
    if len(parts) == 3:
        salt_hex, iters_s, expected = parts
        iters = int(iters_s)
    elif len(parts) == 2:               # eski biçim: salt$hash (200k varsayılan)
        salt_hex, expected = parts
        iters = 200_000
    else:
        return False
    actual = _hash(pw, bytes.fromhex(salt_hex), iters)
    ok = secrets.compare_digest(actual, expected)
    # Eski/zayıf tur sayısıyla özetlenmiş parolayı başarılı girişte yükselt
    if ok and iters != PBKDF2_ITERS:
        set_pin(pw)
    return ok


# ---- Kaba kuvvet kilidi ----

def _recent(ip: str) -> list[float]:
    now = time.time()
    fails = [t for t in _failed.get(ip, []) if now - t < _FAIL_WINDOW]
    if fails:
        _failed[ip] = fails
    else:
        _failed.pop(ip, None)
    return fails


def is_locked(ip: str) -> int:
    """Kilitliyse kalan saniyeyi, değilse 0 döner (son denemeye göre işler)."""
    fails = _recent(ip)
    n = len(fails)
    lock = 0
    for threshold, seconds in _LOCK_TIERS:
        if n >= threshold:
            lock = seconds
            break
    if not lock:
        return 0
    remaining = lock - (time.time() - fails[-1])
    return max(0, math.ceil(remaining))


def record_failure(ip: str) -> None:
    _failed.setdefault(ip, []).append(time.time())


def clear_failures(ip: str) -> None:
    _failed.pop(ip, None)


# ---- Oturum ----

def create_session() -> str:
    token = secrets.token_urlsafe(32)
    database.create_session(token, SESSION_DAYS)
    return token


def session_valid(token: str | None) -> bool:
    if not token:
        return False
    return database.touch_session(token, SESSION_DAYS)


def destroy_session(token: str | None) -> None:
    if token:
        database.delete_session(token)


# ---- İki adımlı doğrulama (TOTP) ----
# Gizli anahtar Fernet ile şifreli saklanır (crypto). Kurtarma kodları yalnızca
# SHA-256 özet olarak tutulur ve tek kullanımlıktır.

def twofa_enabled() -> bool:
    return bool(database.get_setting("totp_secret"))


def twofa_begin(account: str = "meil") -> tuple[str, str]:
    """Yeni bir gizli anahtar üretir, 'pending' olarak (şifreli) saklar.
    (secret, otpauth_uri) döner — henüz etkin değil, doğrulanması gerekir."""
    secret = totp.generate_secret()
    database.set_setting("totp_pending", crypto.encrypt_secret(secret))
    return secret, totp.provisioning_uri(secret, account)


def twofa_activate(code: str) -> list[str] | None:
    """Bekleyen anahtarı verilen kodla doğrular; başarılıysa etkinleştirir ve
    kurtarma kodlarını (düz metin, yalnızca bir kez) döner. Hata → None."""
    pend = database.get_setting("totp_pending")
    if not pend:
        return None
    secret = crypto.decrypt_secret(pend)
    if not totp.verify(secret, code):
        return None
    database.set_setting("totp_secret", crypto.encrypt_secret(secret))
    database.delete_setting("totp_pending")
    codes = totp.generate_recovery_codes()
    database.set_setting("totp_recovery",
                         json.dumps([totp.hash_recovery(c) for c in codes]))
    return codes


def twofa_check(code: str) -> bool:
    """Giriş sırasında: TOTP kodu ya da (tek kullanımlık) kurtarma kodu doğru mu."""
    stored = database.get_setting("totp_secret")
    if not stored:
        return True  # 2FA kapalı
    secret = crypto.decrypt_secret(stored)
    if totp.verify(secret, code):
        return True
    return _use_recovery(code)


def _use_recovery(code: str) -> bool:
    raw = database.get_setting("totp_recovery")
    if not raw:
        return False
    try:
        hashes = json.loads(raw)
    except (ValueError, TypeError):
        return False
    h = totp.hash_recovery(code)
    for stored in hashes:
        if secrets.compare_digest(stored, h):
            hashes.remove(stored)
            database.set_setting("totp_recovery", json.dumps(hashes))
            return True
    return False


def twofa_recovery_left() -> int:
    raw = database.get_setting("totp_recovery")
    if not raw:
        return 0
    try:
        return len(json.loads(raw))
    except (ValueError, TypeError):
        return 0


def twofa_disable() -> None:
    for key in ("totp_secret", "totp_pending", "totp_recovery"):
        database.delete_setting(key)
