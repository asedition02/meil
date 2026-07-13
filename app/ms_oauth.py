"""Microsoft 365 / Outlook.com OAuth2 girişi (cihaz kodu akışı + XOAUTH2).

Microsoft, Exchange Online ve Outlook.com'da IMAP/SMTP için temel kimlik
doğrulamayı (şifreyle giriş) Nisan 2026'da tamamen kapattı. Bu modül MSAL ile
cihaz kodu akışını yürütür: kullanıcı microsoft.com/devicelogin adresinde kodu
girer, dönen jeton önbelleği hesaba şifreli olarak kaydedilir ve her IMAP/SMTP
bağlantısında sessizce yenilenir.
"""
import logging
import threading
import uuid

import msal

from . import config

log = logging.getLogger("meil")

# IMAP + SMTP kapsamları; offline_access'i (yenileme jetonu) MSAL kendisi ekler
SCOPES = [
    "https://outlook.office365.com/IMAP.AccessAsUser.All",
    "https://outlook.office365.com/SMTP.Send",
]

CLIENT_ID_HELP = (
    "Microsoft girişi için sunucuda MS_CLIENT_ID tanımlı olmalı. "
    "Ücretsiz Entra ID uygulama kaydı ~5 dakika sürer — adımlar README'nin "
    "'Microsoft 365 / Outlook hesabı bağlama' bölümünde."
)

# Süren cihaz akışları: flow_id → durum
_flows: dict[str, dict] = {}


def _client_app(cache: msal.SerializableTokenCache | None = None) -> msal.PublicClientApplication:
    if not config.MS_CLIENT_ID:
        raise RuntimeError(CLIENT_ID_HELP)
    return msal.PublicClientApplication(
        config.MS_CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{config.MS_TENANT}",
        token_cache=cache,
    )


def start_device_flow() -> dict:
    """Cihaz kodu akışını başlatır; kullanıcıya gösterilecek kodu döner."""
    cache = msal.SerializableTokenCache()
    app = _client_app(cache)
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        raise RuntimeError(
            f"Cihaz akışı başlatılamadı: {flow.get('error_description') or flow}"
        )
    flow_id = uuid.uuid4().hex
    _flows[flow_id] = {"flow": flow, "app": app, "cache": cache,
                       "result": None, "error": None}
    # acquire_token_by_device_flow kullanıcı kodu girene dek bloklar → ayrı thread
    threading.Thread(target=_wait_for_token, args=(flow_id,), daemon=True).start()
    return {
        "flow_id": flow_id,
        "user_code": flow["user_code"],
        "verification_uri": flow.get("verification_uri", "https://microsoft.com/devicelogin"),
        "expires_in": flow.get("expires_in", 900),
    }


def _wait_for_token(flow_id: str):
    entry = _flows[flow_id]
    try:
        result = entry["app"].acquire_token_by_device_flow(entry["flow"])
        if result and "access_token" in result:
            entry["result"] = result
        else:
            entry["error"] = (result or {}).get("error_description") or "Giriş tamamlanamadı"
    except Exception as e:
        entry["error"] = str(e)


def poll_flow(flow_id: str) -> dict:
    """Akış durumu: pending | error | done (done'da e-posta + jeton önbelleği)."""
    entry = _flows.get(flow_id)
    if not entry:
        return {"status": "error", "error": "Akış bulunamadı veya süresi doldu"}
    if entry["error"]:
        _flows.pop(flow_id, None)
        return {"status": "error", "error": entry["error"]}
    if entry["result"]:
        claims = entry["result"].get("id_token_claims") or {}
        email = claims.get("preferred_username") or claims.get("email") or ""
        cache_blob = entry["cache"].serialize()
        _flows.pop(flow_id, None)
        return {"status": "done", "email": email, "token_cache": cache_blob}
    return {"status": "pending"}


def get_access_token(cache_blob: str) -> tuple[str, str | None]:
    """Kayıtlı önbellekten erişim jetonu üretir.

    Döner: (access_token, güncellenen_önbellek | None). Önbellek değiştiyse
    (jeton yenilendiyse) çağıran taraf yeni değeri hesaba kaydetmelidir.
    """
    cache = msal.SerializableTokenCache()
    try:
        cache.deserialize(cache_blob)
    except Exception:
        raise RuntimeError(
            "Microsoft oturum kaydı bozuk — hesabı kaldırıp yeniden bağlayın."
        )
    app = _client_app(cache)
    accounts = app.get_accounts()
    if not accounts:
        raise RuntimeError(
            "Microsoft oturumu bulunamadı — hesabı kaldırıp yeniden bağlayın."
        )
    result = app.acquire_token_silent(SCOPES, account=accounts[0])
    if not result or "access_token" not in result:
        raise RuntimeError(
            "Microsoft oturumu yenilenemedi (süresi dolmuş veya izinler geri "
            "alınmış olabilir) — hesabı kaldırıp yeniden bağlayın."
        )
    return result["access_token"], (cache.serialize() if cache.has_state_changed else None)
