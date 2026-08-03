"""Web Push bildirimleri: VAPID anahtar yönetimi + tarayıcıya bildirim gönderme.

Hatırlatma, cevap-bekleme ve Donna otomasyon ("bildir") bildirimlerinin
e-posta kanalının yanına eklenen ikinci kanal budur — iOS 16.4+ Safari'de
"Ana Ekrana Ekle" ile kurulmuş PWA'lar dahil, push aboneliği olan her
tarayıcıya anlık bildirim gönderir. E-posta kanalının yerini almaz, üzerine
eklenir; bu modül hiçbir şeyi devre dışı bırakmaz.

VAPID anahtar çifti ilk kullanımda otomatik üretilir ve `settings` tablosunda
saklanır (tıpkı uygulamanın diğer tek-kullanıcılı ayarları gibi) — elle bir
adım gerekmez. İstenirse .env üzerinden VAPID_SUBJECT (push servislerinin
talep ettiği iletişim adresi, ör. "mailto:you@example.com") özelleştirilebilir;
boş bırakılırsa ilk hesabın e-postası kullanılır.

Gönderim her zaman "en iyi çaba" (best-effort): abonelik geçersizleşmişse
(404/410 — kullanıcı bildirimleri kapattı ya da tarayıcı verisini sildi)
sessizce veritabanından silinir; başka bir hata olursa loglanır ama
çağırana yansımaz.
"""
import base64
import json
import logging

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid
from pywebpush import WebPushException, webpush

from . import config, database

log = logging.getLogger("meil.push")


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _generate_keypair() -> tuple[str, str]:
    """Yeni bir VAPID (ECDSA P-256) anahtar çifti üretir.

    Döner: (private_b64, public_b64) — ikisi de ham (raw) bayt dizilerinin
    URL-güvenli base64 hâli. Public anahtar, tarayıcının
    PushManager.subscribe({applicationServerKey}) için beklediği biçimdir.
    """
    vapid = Vapid()
    vapid.generate_keys()
    private_value = vapid.private_key.private_numbers().private_value
    private_b64 = _b64url(private_value.to_bytes(32, "big"))
    public_bytes = vapid.public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    public_b64 = _b64url(public_bytes)
    return private_b64, public_b64


def get_or_create_vapid_keypair() -> tuple[str, str]:
    """(private_b64, public_b64) döner; kayıtlı değilse üretip DB'ye yazar."""
    private_b64 = database.get_setting("vapid_private_key")
    public_b64 = database.get_setting("vapid_public_key")
    if private_b64 and public_b64:
        return private_b64, public_b64
    private_b64, public_b64 = _generate_keypair()
    database.set_setting("vapid_private_key", private_b64)
    database.set_setting("vapid_public_key", public_b64)
    log.info("VAPID anahtar çifti üretildi ve kaydedildi")
    return private_b64, public_b64


def vapid_public_key() -> str:
    """Frontend'in applicationServerKey olarak kullanacağı ham public anahtar."""
    return get_or_create_vapid_keypair()[1]


def _vapid_subject() -> str:
    if config.VAPID_SUBJECT:
        return config.VAPID_SUBJECT
    accounts = database.list_accounts()
    if accounts and accounts[0].get("email"):
        return f"mailto:{accounts[0]['email']}"
    return "mailto:admin@meil.local"


def send_push(title: str, body: str, url: str = "/app") -> int:
    """Kayıtlı tüm push aboneliklerine bildirim gönderir.

    Kaç aboneliğe başarıyla ulaşıldığını döner. Hiçbir abonelik yoksa (henüz
    kimse bildirimleri açmadıysa) hiçbir şey yapmadan 0 döner — VAPID
    anahtarları bile bu durumda üretilmez. Tekil gönderim hataları burada
    yutulur; çağıran fonksiyonların (hatırlatma/cevap-bekleme/otomasyon
    zamanlayıcı işleri) e-posta akışını etkilemez.
    """
    subs = database.list_push_subscriptions()
    if not subs:
        return 0
    private_key, _ = get_or_create_vapid_keypair()
    subject = _vapid_subject()
    payload = json.dumps({"title": title, "body": body, "url": url}, ensure_ascii=False)
    sent = 0
    for sub in subs:
        subscription_info = {
            "endpoint": sub["endpoint"],
            "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
        }
        try:
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=private_key,
                vapid_claims={"sub": subject},
            )
            sent += 1
        except WebPushException as e:
            status = getattr(e.response, "status_code", None)
            if status in (404, 410):
                database.delete_push_subscription(sub["endpoint"])
                log.info("Geçersiz push aboneliği silindi (endpoint sonu: ...%s)",
                         sub["endpoint"][-12:])
            else:
                log.warning("Push gönderilemedi: %s", e)
        except Exception:
            log.exception("Push gönderilemedi (beklenmeyen hata)")
    return sent
