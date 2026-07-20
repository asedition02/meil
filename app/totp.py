"""TOTP (RFC 6238) iki adımlı doğrulama — yalnızca standart kütüphane.

- generate_secret(): base32 gizli anahtar (Authenticator uygulamasına eklenir)
- verify(secret, code): ±1 pencere (30 sn) toleransıyla 6 haneli kodu doğrular
- provisioning_uri(): otpauth:// URI (QR koduna gömülür)
- Kurtarma kodları: tek kullanımlık, SHA-256 ile özetlenip saklanır
"""
import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from urllib.parse import quote


def generate_secret() -> str:
    """160 bitlik rastgele base32 gizli anahtar (dolgu '=' işaretleri atılır)."""
    return base64.b32encode(os.urandom(20)).decode("ascii").rstrip("=")


def _hotp(secret_b32: str, counter: int) -> str:
    pad = "=" * ((8 - len(secret_b32) % 8) % 8)
    key = base64.b32decode(secret_b32.upper() + pad)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{code:06d}"


def verify(secret_b32: str, code: str, window: int = 1) -> bool:
    """6 haneli kodu, geçerli ve komşu zaman dilimlerine karşı sabit zamanlı doğrular."""
    code = (code or "").strip().replace(" ", "")
    if not (code.isdigit() and len(code) == 6):
        return False
    counter = int(time.time()) // 30
    ok = False
    for w in range(-window, window + 1):
        # compare_digest'i her turda çağır — erken çıkışla zamanlama sızıntısı olmasın
        ok = hmac.compare_digest(_hotp(secret_b32, counter + w), code) or ok
    return ok


def provisioning_uri(secret_b32: str, account: str, issuer: str = "Meil") -> str:
    label = quote(f"{issuer}:{account}")
    return (f"otpauth://totp/{label}?secret={secret_b32}"
            f"&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30")


# ---- Kurtarma kodları ----

def generate_recovery_codes(n: int = 10) -> list[str]:
    """xxxx-xxxx-xxxx biçiminde tek kullanımlık kodlar."""
    def one() -> str:
        return "-".join(secrets.token_hex(2) for _ in range(3))
    return [one() for _ in range(n)]


def hash_recovery(code: str) -> str:
    return hashlib.sha256(code.strip().lower().replace(" ", "").encode()).hexdigest()
