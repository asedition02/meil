"""IMAP ile mail çekme, SMTP ile mail gönderme."""
import email
import email.policy
import imaplib
import re
import smtplib
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import parseaddr, parsedate_to_datetime

from . import config


class EmailConfigError(Exception):
    pass


def _require_credentials():
    if not config.EMAIL_ADDRESS or not config.EMAIL_PASSWORD:
        raise EmailConfigError(
            "EMAIL_ADDRESS ve EMAIL_PASSWORD ayarlanmalı. Gmail için uygulama "
            "şifresi oluşturun: https://myaccount.google.com/apppasswords"
        )


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


def fetch_recent(limit: int) -> list[dict]:
    """Gelen kutusundaki en son `limit` maili döndürür (en yeniden eskiye)."""
    _require_credentials()
    conn = imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORT)
    try:
        conn.login(config.EMAIL_ADDRESS, config.EMAIL_PASSWORD)
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


def send_reply(to_address: str, subject: str, body: str, in_reply_to: str | None = None):
    """Onaylanan yanıtı SMTP üzerinden gönderir."""
    _require_credentials()
    msg = EmailMessage()
    msg["From"] = config.EMAIL_ADDRESS
    msg["To"] = to_address
    msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    if in_reply_to and not in_reply_to.startswith("uid:"):
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    msg.set_content(body)
    with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT) as smtp:
        smtp.login(config.EMAIL_ADDRESS, config.EMAIL_PASSWORD)
        smtp.send_message(msg)
