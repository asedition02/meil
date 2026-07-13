"""Hesap ve takvim şifrelerinin simetrik şifrelenmesi (Fernet/AES-128-CBC+HMAC).

Anahtar sırası:
1. MEIL_SECRET_KEY ortam değişkeni (.env) — önerilen: veritabanı dosyası
   sızsa bile anahtar ayrı yerde durur.
2. data/secret.key dosyası — yoksa otomatik üretilir (yalnızca sahibi okuyabilir).

Saklanan değerler "enc:v1:" önekiyle işaretlenir; öneksiz (eski düz metin)
değerler okumada olduğu gibi döner ve init_db açılışta bunları şifreler.
"""
import os

from cryptography.fernet import Fernet, InvalidToken

from . import config

_PREFIX = "enc:v1:"
_fernet: Fernet | None = None


def _load_key() -> bytes:
    env_key = os.environ.get("MEIL_SECRET_KEY", "").strip()
    if env_key:
        return env_key.encode()
    key_file = config.DATA_DIR / "secret.key"
    if key_file.exists():
        return key_file.read_bytes().strip()
    key = Fernet.generate_key()
    key_file.write_bytes(key)
    try:
        os.chmod(key_file, 0o600)
    except OSError:
        pass  # örn. Windows — izin modeli farklı
    return key


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_load_key())
    return _fernet


def encrypt_secret(plain: str) -> str:
    """Şifreyi saklanacak biçime çevirir. Boş ve zaten şifreli değerlere dokunmaz."""
    if not plain or plain.startswith(_PREFIX):
        return plain
    return _PREFIX + _get_fernet().encrypt(plain.encode()).decode()


def decrypt_secret(stored: str) -> str:
    """Saklanan değeri düz metne çevirir; eski (öneksiz) kayıtlar olduğu gibi döner."""
    if not stored or not stored.startswith(_PREFIX):
        return stored or ""
    try:
        return _get_fernet().decrypt(stored[len(_PREFIX):].encode()).decode()
    except InvalidToken:
        raise RuntimeError(
            "Şifre çözülemedi: MEIL_SECRET_KEY veya data/secret.key değişmiş görünüyor. "
            "Eski anahtarı geri yükleyin ya da hesapları silip yeniden ekleyin."
        )


def is_encrypted(stored: str) -> bool:
    return bool(stored) and stored.startswith(_PREFIX)
