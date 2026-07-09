"""Meil — mail tasnif ve yanıt asistanı (FastAPI)."""
import datetime as dt
import json
import logging
import secrets

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import ai, calendar_client, config, database, dataroom, email_client

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("meil")

app = FastAPI(title="Meil — E-posta Asistanı")
database.init_db()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _bootstrap_env_account():
    """.env'de hesap tanımlıysa ve DB boşsa otomatik ekle."""
    if not (config.EMAIL_ADDRESS and config.EMAIL_PASSWORD):
        return
    if database.get_account_by_email(config.EMAIL_ADDRESS):
        return
    database.create_account(
        {
            "display_name": config.EMAIL_ADDRESS,
            "email": config.EMAIL_ADDRESS,
            "password": config.EMAIL_PASSWORD,
            "imap_host": config.IMAP_HOST,
            "imap_port": config.IMAP_PORT,
            "smtp_host": config.SMTP_HOST,
            "smtp_port": config.SMTP_PORT,
            "smtp_security": config.SMTP_SECURITY,
        }
    )
    log.info("Ortam değişkenlerinden hesap eklendi: %s", config.EMAIL_ADDRESS)


_bootstrap_env_account()


class ReplyRequest(BaseModel):
    reply_text: str


class RegenerateRequest(BaseModel):
    instruction: str = ""


class CalendarRequest(BaseModel):
    type: str                 # icloud | ics
    name: str = ""
    username: str = ""        # icloud: Apple ID
    password: str = ""        # icloud: uygulama şifresi
    url: str = ""             # ics: besleme adresi


class EventRequest(BaseModel):
    title: str
    date: str                 # YYYY-MM-DD
    time: str = ""            # HH:MM; boşsa tüm gün
    duration_minutes: int = 60
    location: str = ""
    notes: str = ""
    calendar_id: int | None = None   # None = yerel takvim


class AddToCalendarRequest(BaseModel):
    calendar_id: int | None = None
    title: str = ""
    date: str = ""
    time: str = ""
    duration_minutes: int = 0


class AccountRequest(BaseModel):
    display_name: str = ""
    email: str
    password: str
    provider: str = "custom"  # gmail | outlook | yahoo | yandex | custom
    imap_host: str = ""
    imap_port: int = 993
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_security: str = "ssl"  # ssl | starttls


def _account_dict(req: AccountRequest) -> dict:
    preset = email_client.PRESETS.get(req.provider, {})
    return {
        "display_name": req.display_name.strip() or req.email,
        "email": req.email.strip(),
        "password": req.password,
        "imap_host": preset.get("imap_host") or req.imap_host.strip(),
        "imap_port": preset.get("imap_port") or req.imap_port,
        "smtp_host": preset.get("smtp_host") or req.smtp_host.strip(),
        "smtp_port": preset.get("smtp_port") or req.smtp_port,
        "smtp_security": preset.get("smtp_security") or req.smtp_security,
    }


# ---- Hesaplar ----

@app.get("/api/accounts")
def get_accounts():
    return {"accounts": database.list_accounts(), "presets": list(email_client.PRESETS)}


@app.post("/api/accounts")
def add_account(req: AccountRequest):
    """Hesabı ekler; önce IMAP+SMTP girişini test eder."""
    account = _account_dict(req)
    if database.get_account_by_email(account["email"]):
        raise HTTPException(status_code=409, detail="Bu adres zaten ekli")
    try:
        email_client.test_login(account)
    except (email_client.EmailConfigError, email_client.EmailAuthError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Sunucuya bağlanılamadı: {e}")
    account_id = database.create_account(account)
    return {"ok": True, "id": account_id}


@app.delete("/api/accounts/{account_id}")
def remove_account(account_id: int):
    if not database.get_account(account_id):
        raise HTTPException(status_code=404, detail="Hesap bulunamadı")
    database.delete_account(account_id)
    return {"ok": True}


# ---- Eşitleme ----

def _sync_account(account: dict) -> dict:
    messages = email_client.fetch_recent(account, config.SYNC_LIMIT)
    new_count, errors = 0, []
    for msg in messages:
        if database.email_exists(msg["message_id"], account["id"]):
            continue
        raw_attachments = msg.pop("raw_attachments", [])
        saved = dataroom.save_attachments(msg["sender_email"], msg["date"], raw_attachments)
        msg["attachments"] = saved
        try:
            triage = ai.triage_email(
                sender=f"{msg['sender_name']} <{msg['sender_email']}>",
                subject=msg["subject"],
                date=msg["date"],
                body=msg["body_text"],
                attachments=[a["filename"] for a in saved],
                user_name=config.USER_NAME,
            )
            msg.update(triage)
            event = msg.pop("detected_event", None)
            if event and event.get("exists") and event.get("date"):
                msg["event_json"] = json.dumps(event, ensure_ascii=False)
        except Exception as e:
            log.exception("Tasnif hatası: %s", msg["subject"])
            errors.append(f"{msg['subject']}: {e}")
            msg.update(
                {
                    "category": "Diğer",
                    "priority": "orta",
                    "summary": "(Otomatik tasnif yapılamadı)",
                    "needs_reply": False,
                    "suggested_reply": "",
                }
            )
        database.insert_email(msg)
        new_count += 1
    return {"account": account["email"], "new_emails": new_count,
            "checked": len(messages), "errors": errors}


@app.post("/api/sync")
def sync_emails(account_id: int | None = None):
    """Tüm hesaplardan (veya tek hesaptan) yeni mailleri çeker ve tasnif eder."""
    accounts = (
        [database.get_account(account_id)] if account_id else database.list_accounts(include_password=True)
    )
    accounts = [a for a in accounts if a]
    if not accounts:
        raise HTTPException(
            status_code=400,
            detail="Kayıtlı hesap yok. Hesaplar sekmesinden bir mail hesabı ekleyin.",
        )
    results, total_new = [], 0
    for account in accounts:
        try:
            r = _sync_account(account)
        except (email_client.EmailConfigError, email_client.EmailAuthError) as e:
            r = {"account": account["email"], "new_emails": 0, "checked": 0, "errors": [str(e)]}
        except Exception as e:
            r = {"account": account["email"], "new_emails": 0, "checked": 0,
                 "errors": [f"Bağlantı hatası: {e}"]}
        total_new += r["new_emails"]
        results.append(r)
    return {"new_emails": total_new, "results": results}


# ---- Mailler ----

class FlagRequest(BaseModel):
    value: bool


class SnoozeRequest(BaseModel):
    until: str = ""           # ISO tarih-saat; boş = ertelemeyi kaldır


class ComposeRequest(BaseModel):
    account_id: int
    to: str
    cc: str = ""
    subject: str = ""
    body: str
    email_id: int | None = None   # yanıt olarak gönderiliyorsa


class ComposeDraftRequest(BaseModel):
    instruction: str
    to: str = ""
    subject: str = ""


@app.get("/api/emails")
def list_emails(category: str | None = None, status: str | None = None,
                account_id: int | None = None, view: str = "inbox"):
    return {
        "emails": database.list_emails(category=category, status=status,
                                       account_id=account_id, view=view),
        "counts": database.category_counts(account_id=account_id),
        "views": database.view_counts(account_id=account_id),
        "categories": ai.CATEGORIES,
    }


@app.post("/api/emails/{email_id}/read")
def mark_read(email_id: int, req: FlagRequest):
    if not database.get_email(email_id):
        raise HTTPException(status_code=404, detail="Mail bulunamadı")
    database.update_email(email_id, is_read=1 if req.value else 0)
    return {"ok": True}


@app.post("/api/emails/{email_id}/star")
def mark_starred(email_id: int, req: FlagRequest):
    if not database.get_email(email_id):
        raise HTTPException(status_code=404, detail="Mail bulunamadı")
    database.update_email(email_id, starred=1 if req.value else 0)
    return {"ok": True}


@app.post("/api/emails/{email_id}/snooze")
def snooze_email(email_id: int, req: SnoozeRequest):
    if not database.get_email(email_id):
        raise HTTPException(status_code=404, detail="Mail bulunamadı")
    if req.until:
        try:
            dt.datetime.fromisoformat(req.until)
        except ValueError:
            raise HTTPException(status_code=400, detail="Geçersiz tarih")
    database.update_email(email_id, snooze_until=req.until or None)
    return {"ok": True}


@app.post("/api/emails/{email_id}/unarchive")
def unarchive_email(email_id: int):
    if not database.get_email(email_id):
        raise HTTPException(status_code=404, detail="Mail bulunamadı")
    database.update_email(email_id, status="new")
    return {"ok": True}


@app.post("/api/compose")
def compose_send(req: ComposeRequest):
    """Sıfırdan yeni mail gönderir."""
    account = database.get_account(req.account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Hesap bulunamadı")
    if not req.to.strip() or "@" not in req.to:
        raise HTTPException(status_code=400, detail="Geçerli bir alıcı adresi girin")
    if not req.body.strip():
        raise HTTPException(status_code=400, detail="Mail metni boş olamaz")
    try:
        email_client.send_message(
            account, req.to.strip(), req.subject.strip() or "(konu yok)",
            req.body, cc=req.cc,
        )
    except (email_client.EmailConfigError, email_client.EmailAuthError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gönderim başarısız: {e}")
    return {"ok": True}


@app.post("/api/compose/draft")
def compose_draft(req: ComposeDraftRequest):
    """Talimattan AI ile mail taslağı üretir."""
    if not req.instruction.strip():
        raise HTTPException(status_code=400, detail="Ne yazılacağını kısaca anlatın")
    try:
        draft = ai.compose_email(req.instruction, req.to, req.subject, config.USER_NAME)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Taslak üretilemedi: {e}")
    return draft


@app.get("/api/emails/{email_id}")
def get_email(email_id: int):
    email_data = database.get_email(email_id)
    if not email_data:
        raise HTTPException(status_code=404, detail="Mail bulunamadı")
    if not email_data["is_read"]:
        database.update_email(email_id, is_read=1)  # açılınca okundu say
        email_data["is_read"] = True
    return email_data


@app.post("/api/emails/{email_id}/send")
def send_reply(email_id: int, req: ReplyRequest):
    """Kullanıcının onayladığı yanıtı, maili alan hesaptan gönderir."""
    email_data = database.get_email(email_id)
    if not email_data:
        raise HTTPException(status_code=404, detail="Mail bulunamadı")
    if not req.reply_text.strip():
        raise HTTPException(status_code=400, detail="Yanıt metni boş olamaz")
    account = database.get_account(email_data["account_id"]) if email_data["account_id"] else None
    if not account:
        accounts = database.list_accounts(include_password=True)
        if len(accounts) == 1:
            account = accounts[0]
        else:
            raise HTTPException(
                status_code=400,
                detail="Bu mailin hangi hesaba ait olduğu belirlenemedi. Hesabı silip yeniden ekleyin ve maili tekrar eşitleyin.",
            )
    try:
        email_client.send_reply(
            account=account,
            to_address=email_data["sender_email"],
            subject=email_data["subject"] or "",
            body=req.reply_text,
            in_reply_to=email_data["message_id"],
        )
    except (email_client.EmailConfigError, email_client.EmailAuthError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gönderim başarısız: {e}")
    database.update_email(email_id, status="replied", suggested_reply=req.reply_text)
    return {"ok": True}


@app.post("/api/emails/{email_id}/regenerate")
def regenerate(email_id: int, req: RegenerateRequest):
    """Yanıt taslağını (isteğe bağlı talimatla) yeniden üretir."""
    email_data = database.get_email(email_id)
    if not email_data:
        raise HTTPException(status_code=404, detail="Mail bulunamadı")
    try:
        reply = ai.regenerate_reply(
            sender=f"{email_data['sender_name']} <{email_data['sender_email']}>",
            subject=email_data["subject"] or "",
            date=email_data["date"] or "",
            body=email_data["body_text"] or "",
            instruction=req.instruction,
            user_name=config.USER_NAME,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Taslak üretilemedi: {e}")
    database.update_email(email_id, suggested_reply=reply, needs_reply=1)
    return {"suggested_reply": reply}


@app.post("/api/emails/{email_id}/archive")
def archive_email(email_id: int):
    if not database.get_email(email_id):
        raise HTTPException(status_code=404, detail="Mail bulunamadı")
    database.update_email(email_id, status="archived")
    return {"ok": True}


# ---- Takvimler ----

SYNC_PAST_DAYS = 30
SYNC_FUTURE_DAYS = 365


@app.get("/api/calendars")
def get_calendars():
    return {"calendars": database.list_calendars()}


@app.post("/api/calendars")
def add_calendar(req: CalendarRequest):
    """Takvim kaynağı ekler. icloud: hesaptaki TÜM takvimleri keşfedip ekler."""
    if req.type == "icloud":
        if not req.username or not req.password:
            raise HTTPException(status_code=400, detail="Apple ID ve uygulama şifresi gerekli")
        try:
            discovered = calendar_client.discover_icloud(req.username.strip(), req.password)
        except calendar_client.CalendarError as e:
            raise HTTPException(status_code=400, detail=str(e))
        added = []
        for cal in discovered:
            database.create_calendar(
                {
                    "name": cal["name"],
                    "type": "icloud",
                    "url": cal["url"],
                    "username": req.username.strip(),
                    "password": req.password,
                }
            )
            added.append(cal["name"])
        return {"ok": True, "added": added}

    if req.type == "ics":
        if not req.url.strip():
            raise HTTPException(status_code=400, detail="ICS adresi gerekli")
        try:
            calendar_client.test_ics(req.url)
        except calendar_client.CalendarError as e:
            raise HTTPException(status_code=400, detail=str(e))
        name = req.name.strip() or "ICS Takvimi"
        database.create_calendar({"name": name, "type": "ics", "url": req.url.strip()})
        return {"ok": True, "added": [name]}

    raise HTTPException(status_code=400, detail="Bilinmeyen takvim türü")


@app.delete("/api/calendars/{calendar_id}")
def remove_calendar(calendar_id: int):
    if not database.get_calendar(calendar_id):
        raise HTTPException(status_code=404, detail="Takvim bulunamadı")
    database.delete_calendar(calendar_id)
    return {"ok": True}


@app.post("/api/calendars/sync")
def sync_calendars():
    """Tüm harici takvimlerin etkinliklerini yeniden çeker."""
    calendars = [c for c in database.list_calendars(include_password=True) if c["type"] != "local"]
    if not calendars:
        raise HTTPException(status_code=400, detail="Kayıtlı harici takvim yok.")
    start = dt.datetime.now() - dt.timedelta(days=SYNC_PAST_DAYS)
    end = dt.datetime.now() + dt.timedelta(days=SYNC_FUTURE_DAYS)
    results, total = [], 0
    for cal in calendars:
        try:
            events = calendar_client.fetch_events(cal, start, end)
            database.replace_synced_events(cal["id"], events)
            total += len(events)
            results.append({"calendar": cal["name"], "events": len(events), "error": None})
        except calendar_client.CalendarError as e:
            results.append({"calendar": cal["name"], "events": 0, "error": str(e)})
    return {"total_events": total, "results": results}


def _build_times(date_str: str, time_str: str, duration_minutes: int) -> tuple[dt.datetime, dt.datetime, bool]:
    try:
        day = dt.date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz tarih (YYYY-AA-GG bekleniyor)")
    if time_str:
        try:
            t = dt.time.fromisoformat(time_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="Geçersiz saat (SS:DD bekleniyor)")
        start = dt.datetime.combine(day, t)
        end = start + dt.timedelta(minutes=duration_minutes or 60)
        return start, end, False
    start = dt.datetime.combine(day, dt.time.min)
    return start, start + dt.timedelta(days=1), True


def _create_event(title: str, start: dt.datetime, end: dt.datetime, all_day: bool,
                  location: str, notes: str, calendar_id: int | None,
                  source: str, source_email_id: int | None = None) -> dict:
    """Etkinliği yerel takvime veya seçilen iCloud takvimine yazar."""
    target_name = "Meil (yerel)"
    uid = None
    if calendar_id:
        cal = database.get_calendar(calendar_id)
        if not cal:
            raise HTTPException(status_code=404, detail="Takvim bulunamadı")
        target_name = cal["name"]
        if cal["type"] == "icloud":
            try:
                uid = calendar_client.create_caldav_event(
                    cal, title, start, end, location or None, notes or None
                )
            except calendar_client.CalendarError as e:
                raise HTTPException(status_code=502, detail=str(e))
        elif cal["type"] == "ics":
            raise HTTPException(
                status_code=400,
                detail="ICS takvimleri salt okunurdur; etkinliği yerel takvime veya iCloud'a ekleyin.",
            )
    database.insert_event(
        {
            "calendar_id": calendar_id,
            "uid": uid,
            "title": title,
            "start": start.isoformat(timespec="minutes"),
            "end": end.isoformat(timespec="minutes"),
            "all_day": all_day,
            "location": location or None,
            "notes": notes or None,
            # iCloud'a yazılanlar bir sonraki eşitlemede sunucudan gelir
            "source": "sync" if uid else source,
            "source_email_id": source_email_id,
        }
    )
    return {"ok": True, "calendar": target_name}


@app.get("/api/events")
def get_events(start: str, end: str):
    return {
        "events": database.list_events(start, end),
        "calendars": database.list_calendars(),
    }


@app.post("/api/events")
def create_event(req: EventRequest):
    if not req.title.strip():
        raise HTTPException(status_code=400, detail="Etkinlik başlığı gerekli")
    start, end, all_day = _build_times(req.date, req.time, req.duration_minutes)
    return _create_event(req.title.strip(), start, end, all_day,
                         req.location.strip(), req.notes.strip(), req.calendar_id, "manual")


@app.delete("/api/events/{event_id}")
def remove_event(event_id: int):
    ev = database.get_event(event_id)
    if not ev:
        raise HTTPException(status_code=404, detail="Etkinlik bulunamadı")
    database.delete_event(event_id)
    return {"ok": True}


@app.post("/api/emails/{email_id}/add-to-calendar")
def add_email_event(email_id: int, req: AddToCalendarRequest):
    """Mailde tespit edilen etkinliği takvime ekler."""
    email_data = database.get_email(email_id)
    if not email_data:
        raise HTTPException(status_code=404, detail="Mail bulunamadı")
    detected = email_data.get("event") or {}
    title = (req.title or detected.get("title") or email_data["subject"] or "Etkinlik").strip()
    date_str = req.date or detected.get("date") or ""
    if not date_str:
        raise HTTPException(status_code=400, detail="Etkinlik tarihi yok")
    time_str = req.time or detected.get("time") or ""
    duration = req.duration_minutes or detected.get("duration_minutes") or 60
    start, end, all_day = _build_times(date_str, time_str, duration)
    notes = f"Mailden eklendi: {email_data['sender_email']} — {email_data['subject']}"
    return _create_event(title, start, end, all_day,
                         (detected.get("location") or "").strip(), notes,
                         req.calendar_id, "email", source_email_id=email_id)


# ---- Dataroom ----

class NoteRequest(BaseModel):
    path: str
    note: str = ""
    tags: str = ""


class AddNoteRequest(BaseModel):
    path: str
    author: str = ""
    content: str


class ShareRequest(BaseModel):
    path: str
    expires_days: int = 0     # 0 = süresiz


class FavoriteRequest(BaseModel):
    path: str
    favorite: bool


class FolderRequest(BaseModel):
    folder: str


class MoveRequest(BaseModel):
    path: str
    folder: str


class ZipRequest(BaseModel):
    paths: list[str]


class BulkDeleteRequest(BaseModel):
    paths: list[str]


class SendFileRequest(BaseModel):
    path: str
    to: str
    subject: str = ""
    message: str = ""
    account_id: int | None = None


def _resolve_or_404(path: str):
    try:
        return dataroom.resolve_file(path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dosya bulunamadı")


@app.get("/api/dataroom")
def dataroom_files():
    files = dataroom.list_files()
    meta = database.all_file_meta()
    shared_count, total_size = 0, 0
    for f in files:
        m = meta.get(f["path"], {})
        f["note"] = m.get("note") or ""
        f["tags"] = [t.strip() for t in (m.get("tags") or "").split(",") if t.strip()]
        f["favorite"] = bool(m.get("favorite"))
        f["share_token"] = m.get("share_token")
        f["share_expires"] = m.get("share_expires")
        f["share_downloads"] = m.get("share_downloads") or 0
        if f["share_token"]:
            shared_count += 1
        total_size += f["size"]
    return {
        "files": files,
        "folders": dataroom.list_folders(),
        "activity": database.list_activity(),
        "stats": {"count": len(files), "size": total_size, "shared": shared_count},
    }


@app.get("/api/dataroom/download")
def dataroom_download(path: str):
    target = _resolve_or_404(path)
    database.log_activity("download", path)
    return FileResponse(target, filename=target.name)


@app.get("/api/dataroom/view")
def dataroom_view(path: str):
    """Tarayıcıda önizleme (indirme yerine satır içi gösterim)."""
    target = _resolve_or_404(path)
    return FileResponse(target, filename=target.name, content_disposition_type="inline")


@app.post("/api/dataroom/upload")
async def dataroom_upload(files: list[UploadFile] = File(...), folder: str = Form("")):
    """Kullanıcının kendi dosyalarını dataroom'a yüklemesi."""
    target_folder = folder.strip() or f"Yüklemelerim/{dt.date.today().isoformat()}"
    saved = []
    for f in files:
        content = await f.read()
        if not content or not f.filename:
            continue
        s = dataroom.save_upload(target_folder, f.filename, content)
        database.log_activity("upload", s["path"])
        saved.append(s)
    if not saved:
        raise HTTPException(status_code=400, detail="Yüklenecek dosya yok")
    return {"ok": True, "files": saved}


@app.post("/api/dataroom/folder")
def dataroom_create_folder(req: FolderRequest):
    if not req.folder.strip():
        raise HTTPException(status_code=400, detail="Klasör adı gerekli")
    created = dataroom.create_folder(req.folder)
    database.log_activity("folder", created)
    return {"ok": True, "folder": created}


@app.post("/api/dataroom/move")
def dataroom_move(req: MoveRequest):
    _resolve_or_404(req.path)
    new_path = dataroom.move_file(req.path, req.folder)
    database.update_meta_path(req.path, new_path)
    database.log_activity("move", new_path, detail=f"{req.path} → {new_path}")
    return {"ok": True, "path": new_path}


@app.delete("/api/dataroom/file")
def dataroom_delete(path: str):
    _resolve_or_404(path)
    dataroom.delete_file(path)
    database.delete_file_meta(path)
    database.log_activity("delete", path)
    return {"ok": True}


@app.post("/api/dataroom/bulk-delete")
def dataroom_bulk_delete(req: BulkDeleteRequest):
    deleted = 0
    for path in req.paths:
        try:
            dataroom.delete_file(path)
            database.delete_file_meta(path)
            database.log_activity("delete", path)
            deleted += 1
        except FileNotFoundError:
            continue
    return {"ok": True, "deleted": deleted}


@app.post("/api/dataroom/zip")
def dataroom_zip(req: ZipRequest):
    """Seçili dosyaları tek ZIP olarak indirir."""
    if not req.paths:
        raise HTTPException(status_code=400, detail="Dosya seçilmedi")
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path in req.paths:
            target = _resolve_or_404(path)
            z.write(target, arcname=path)
            database.log_activity("download", path, detail="zip")
    buf.seek(0)
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="dataroom.zip"'},
    )


@app.post("/api/dataroom/note")
def dataroom_note(req: NoteRequest):
    """Dosyanın sabit açıklaması + etiketleri."""
    _resolve_or_404(req.path)
    database.set_file_note(req.path, req.note.strip())
    database.set_file_tags(req.path, req.tags.strip())
    database.log_activity("note", req.path)
    return {"ok": True}


@app.post("/api/dataroom/favorite")
def dataroom_favorite(req: FavoriteRequest):
    _resolve_or_404(req.path)
    database.set_favorite(req.path, req.favorite)
    return {"ok": True}


@app.get("/api/dataroom/notes")
def dataroom_get_notes(path: str):
    """Dosyanın tüm notlarını getirir (yazarlı not akışı)."""
    _resolve_or_404(path)
    notes = database.get_file_notes(path)
    return {"notes": notes}


@app.post("/api/dataroom/notes")
def dataroom_add_note(req: AddNoteRequest):
    """Dosyaya yeni not ekler."""
    _resolve_or_404(req.path)
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="Not boş olamaz")
    note = database.add_file_note(req.path, req.author.strip(), req.content.strip())
    database.log_activity("note", req.path)
    return {"ok": True, "note": note}


@app.delete("/api/dataroom/notes/{note_id}")
def dataroom_delete_note(note_id: int):
    """Bir notu siler."""
    database.delete_file_note(note_id)
    return {"ok": True}


@app.post("/api/dataroom/share")
def dataroom_share(req: ShareRequest):
    """Paylaşım linki oluşturur; istenirse süreli."""
    _resolve_or_404(req.path)
    info = database.get_share_info(req.path) or {}
    token = info.get("share_token")
    expires = None
    if req.expires_days > 0:
        expires = (dt.datetime.now() + dt.timedelta(days=req.expires_days)).isoformat(timespec="minutes")
    if not token:
        token = secrets.token_urlsafe(16)
        database.set_share_token(req.path, token, expires)
        database.log_activity("share_created", req.path,
                              detail=f"{req.expires_days} gün" if expires else "süresiz")
        downloads = 0
    else:
        downloads = info.get("share_downloads") or 0
        expires = info.get("share_expires")
    return {"ok": True, "token": token, "url": f"/share/{token}",
            "expires": expires, "downloads": downloads}


@app.delete("/api/dataroom/share")
def dataroom_unshare(path: str):
    database.clear_share_token(path)
    database.log_activity("share_revoked", path)
    return {"ok": True}


@app.get("/share/{token}")
def shared_file(token: str):
    """Paylaşım linki — giriş gerektirmez; linki bilen dosyayı indirebilir."""
    info = database.get_share_by_token(token)
    if not info:
        raise HTTPException(status_code=404, detail="Link geçersiz veya iptal edilmiş")
    if info.get("share_expires") and info["share_expires"] < dt.datetime.now().isoformat():
        raise HTTPException(status_code=404, detail="Linkin süresi dolmuş")
    try:
        target = dataroom.resolve_file(info["path"])
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dosya artık mevcut değil")
    database.increment_share_downloads(info["path"])
    database.log_activity("share_download", info["path"])
    return FileResponse(target, filename=target.name)


@app.post("/api/dataroom/send")
def dataroom_send(req: SendFileRequest):
    """Dataroom'daki bir belgeyi mail eki olarak gönderir."""
    target = _resolve_or_404(req.path)
    if not req.to.strip() or "@" not in req.to:
        raise HTTPException(status_code=400, detail="Geçerli bir alıcı adresi girin")
    if req.account_id:
        account = database.get_account(req.account_id)
    else:
        accounts = database.list_accounts(include_password=True)
        account = accounts[0] if len(accounts) == 1 else None
    if not account:
        raise HTTPException(status_code=400, detail="Gönderen hesap seçin")
    subject = req.subject.strip() or f"Belge: {target.name}"
    body = req.message.strip() or f"Merhaba,\n\n{target.name} dosyası ekte iletilmiştir.\n\nİyi çalışmalar"
    try:
        email_client.send_message(
            account, req.to.strip(), subject, body,
            attachments=[(target.name, target.read_bytes())],
        )
    except (email_client.EmailConfigError, email_client.EmailAuthError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gönderim başarısız: {e}")
    database.log_activity("send", req.path, detail=req.to.strip())
    return {"ok": True}


# Arayüz (static/app.js) ile el sıkışma için — her API değişikliğinde artırılır.
API_VERSION = 8


@app.get("/api/status")
def status():
    accounts = database.list_accounts()
    return {
        "api_version": API_VERSION,
        "accounts": len(accounts),
        "ai_configured": bool(config.ANTHROPIC_API_KEY),
        "model": config.CLAUDE_MODEL,
    }


app.mount("/", StaticFiles(directory=config.BASE_DIR / "static", html=True), name="static")
