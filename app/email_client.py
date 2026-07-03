"""IMAP ile mail çekme, SMTP ile mail gönderme — hesap bazlı."""
import email
import email.policy
import imaplib
import re
import smtplib
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import parseaddr, parsedate_to_datetime


class EmailConfigError(Exception):
    pass


class EmailAuthError(Exception):
    pass


# Bilinen sağlayıcı ayarları — "Şirket / Özel" için kullanıcı kendisi girer
PRESETS = {
    "gmail": {
        "imap_host": "imap.gmail.com", "imap_port": 993,
        "smtp_host": "smtp.gmail.com", "smtp_port": 465, "smtp_security": "ssl",
    },
    "outlook": {
        "imap_host": "outlook.office365.com", "imap_port": 993,
        "smtp_host": "smtp.office365.com", "smtp_port": 587, "smtp_security": "starttls",
    },
    "yahoo": {
        "imap_host": "imap.mail.yahoo.com", "imap_port": 993,
        "smtp_host": "smtp.mail.yahoo.com", "smtp_port": 465, "smtp_security": "ssl",
    },
    "yandex": {
        "imap_host": "imap.yandex.com", "imap_port": 993,
        "smtp_host": "smtp.yandex.com", "smtp_port": 465, "smtp_security": "ssl",
    },
}


def auth_help(account_email: str) -> str:
    return (
        f"{account_email} için giriş reddedildi. Kontrol listesi: "
        "1) Gmail/Yahoo/Yandex için normal şifre değil, UYGULAMA ŞİFRESİ gerekir. "
        "2) Şirket maili için IMAP erişiminin açık olduğunu BT ekibinize sorun. "
        "3) Sunucu adreslerini ve portları kontrol edin."
    )


def _normalize_password(password: str) -> str:
    """Google uygulama şifresi 'xxxx xxxx xxxx xxxx' biçiminde yapıştırılırsa boşlukları sil."""
    password = password.strip()
    if re.fullmatch(r"([A-Za-z]{4} ){3}[A-Za-z]{4}", password):
        password = password.replace(" ", "")
    return password


def _validate(account: dict):
    for key in ("email", "password", "imap_host", "smtp_host"):
        if not account.get(key):
            raise EmailConfigError(f"Hesap ayarı eksik: {key}")


def _decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _html_to_text(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?</\1>", "", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|tr|li|h[1-6])>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_body(msg: email.message.Message) -> str:
    """text/plain tercih edilir; yoksa HTML'den metin çıkarılır."""
    plain, html = None, None
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        if part.get_content_disposition() == "attachment":
            continue
        ctype = part.get_content_type()
        if ctype not in ("text/plain", "text/html"):
            continue
        try:
            payload = part.get_payload(decode=True)
            charset = part.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="replace")
        except Exception:
            continue
        if ctype == "text/plain" and plain is None:
            plain = text
        elif ctype == "text/html" and html is None:
            html = text
    if plain:
        return plain.strip()
    if html:
        return _html_to_text(html)
    return ""


def _extract_attachments(msg: email.message.Message) -> list[tuple[str, bytes]]:
    """(dosya_adı, içerik) listesi döner."""
    out = []
    for part in msg.walk():
        if part.get_content_disposition() != "attachment":
            continue
        filename = _decode(part.get_filename())
        payload = part.get_payload(decode=True)
        if filename and payload:
            out.append((filename, payload))
    return out


def _imap_login(account: dict) -> imaplib.IMAP4_SSL:
    conn = imaplib.IMAP4_SSL(account["imap_host"], int(account.get("imap_port") or 993))
    try:
        conn.login(account["email"], _normalize_password(account["password"]))
    except imaplib.IMAP4.error as e:
        try:
            conn.logout()
        except Exception:
            pass
        if "AUTHENTICATIONFAILED" in str(e).upper():
            raise EmailAuthError(auth_help(account["email"])) from e
        raise
    return conn


def test_login(account: dict):
    """Hesap eklerken IMAP ve SMTP girişini doğrular."""
    _validate(account)
    conn = _imap_login(account)
    try:
        conn.select("INBOX", readonly=True)
    finally:
        try:
            conn.logout()
        except Exception:
            pass
    with _smtp_connect(account) as smtp:
        pass  # login başarılıysa yeterli


def fetch_recent(account: dict, limit: int) -> list[dict]:
    """Hesabın gelen kutusundaki en son `limit` maili döndürür."""
    _validate(account)
    conn = _imap_login(account)
    try:
        conn.select("INBOX", readonly=True)
        status, data = conn.uid("SEARCH", None, "ALL")
        if status != "OK":
            return []
        uids = data[0].split()
        results = []
        for uid in reversed(uids[-limit * 2 :]):  # yenilerden başla
            if len(results) >= limit:
                break
            status, msg_data = conn.uid("FETCH", uid, "(RFC822)")
            if status != "OK" or not msg_data or msg_data[0] is None:
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw, policy=email.policy.default)
            sender_name, sender_email = parseaddr(_decode(msg.get("From")))
            try:
                date = parsedate_to_datetime(msg.get("Date")).isoformat()
            except Exception:
                date = msg.get("Date", "")
            results.append(
                {
                    "account_id": account.get("id"),
                    "imap_uid": uid.decode(),
                    "message_id": msg.get("Message-ID", "").strip() or f"uid:{uid.decode()}",
                    "sender_name": sender_name,
                    "sender_email": sender_email,
                    "subject": _decode(msg.get("Subject")),
                    "date": date,
                    "body_text": _extract_body(msg),
                    "raw_attachments": _extract_attachments(msg),
                }
            )
        return results
    finally:
        try:
            conn.logout()
        except Exception:
            pass


def _smtp_connect(account: dict) -> smtplib.SMTP:
    host = account["smtp_host"]
    port = int(account.get("smtp_port") or 465)
    security = account.get("smtp_security") or "ssl"
    if security == "starttls":
        smtp = smtplib.SMTP(host, port, timeout=30)
        smtp.starttls()
    else:
        smtp = smtplib.SMTP_SSL(host, port, timeout=30)
    try:
        smtp.login(account["email"], _normalize_password(account["password"]))
    except smtplib.SMTPAuthenticationError as e:
        smtp.close()
        raise EmailAuthError(auth_help(account["email"])) from e
    return smtp


def send_reply(account: dict, to_address: str, subject: str, body: str,
               in_reply_to: str | None = None):
    """Onaylanan yanıtı, maili alan hesabın SMTP sunucusundan gönderir."""
    _validate(account)
    msg = EmailMessage()
    msg["From"] = account["email"]
    msg["To"] = to_address
    msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    if in_reply_to and not in_reply_to.startswith("uid:"):
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    msg.set_content(body)
    with _smtp_connect(account) as smtp:
        smtp.send_message(msg)
