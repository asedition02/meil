"""SQLite veri katmanı."""
import json
import re
import sqlite3
from contextlib import contextmanager

from . import config, crypto

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name TEXT,
    email TEXT UNIQUE,
    password TEXT,                      -- şifreli: parola ya da OAuth jeton önbelleği
    imap_host TEXT,
    imap_port INTEGER DEFAULT 993,
    smtp_host TEXT,
    smtp_port INTEGER DEFAULT 465,
    smtp_security TEXT DEFAULT 'ssl',   -- ssl | starttls
    auth_type TEXT DEFAULT 'password',  -- password | oauth-ms
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER,
    message_id TEXT,
    imap_uid TEXT,
    sender_name TEXT,
    sender_email TEXT,
    subject TEXT,
    date TEXT,
    body_text TEXT,
    category TEXT,
    priority TEXT,
    summary TEXT,
    needs_reply INTEGER DEFAULT 0,
    suggested_reply TEXT,
    status TEXT DEFAULT 'new',          -- new | replied | archived
    attachments TEXT DEFAULT '[]',      -- JSON: [{filename, path, size}]
    event_json TEXT,                    -- AI'nın tespit ettiği etkinlik (JSON)
    is_read INTEGER DEFAULT 0,
    starred INTEGER DEFAULT 0,
    snooze_until TEXT,                  -- ISO tarih-saat; ertelenen mailler
    in_reply_to TEXT,                   -- yanıtlanan mailin Message-ID'si
    refs TEXT,                          -- References başlığı (kök → ebeveyn zinciri)
    thread_id TEXT,                     -- konuşma anahtarı: zincirin kök Message-ID'si
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_emails_thread ON emails(account_id, thread_id);

CREATE TABLE IF NOT EXISTS calendars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    type TEXT,                          -- icloud | ics | local
    url TEXT,
    username TEXT,
    password TEXT,
    color TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    calendar_id INTEGER,                -- NULL = yerel Meil takvimi
    uid TEXT,
    title TEXT,
    start TEXT,                         -- ISO tarih-saat
    end TEXT,
    all_day INTEGER DEFAULT 0,
    location TEXT,
    notes TEXT,
    source TEXT DEFAULT 'manual',       -- sync | manual | email
    source_email_id INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_events_start ON events(start);
CREATE INDEX IF NOT EXISTS idx_events_calendar ON events(calendar_id);

CREATE TABLE IF NOT EXISTS dataroom_meta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE,                   -- dataroom köküne göre dosya yolu
    note TEXT,
    tags TEXT,                          -- virgülle ayrılmış etiketler
    favorite INTEGER DEFAULT 0,
    share_token TEXT UNIQUE,
    share_expires TEXT,                 -- ISO tarih; NULL = süresiz
    share_downloads INTEGER DEFAULT 0,
    doc_type TEXT,                      -- AI analizi: Fatura | Sözleşme | ...
    doc_date TEXT,                      -- belgenin kendi tarihi (YYYY-MM-DD)
    doc_amount TEXT,                    -- fatura ise tutar + para birimi
    ai_summary TEXT,                    -- AI'nın 1-2 cümlelik özeti
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS dataroom_text (
    path TEXT PRIMARY KEY,              -- dosya yolu
    content TEXT,                       -- çıkarılan düz metin
    mtime REAL,                         -- kaynağın değişim zamanı (yeniden tarama için)
    extracted_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS dataroom_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT,                        -- upload | delete | note | tags | share_created |
                                        -- share_revoked | share_download | send | move |
                                        -- folder | download
    path TEXT,
    detail TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS dataroom_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT,
    author TEXT,
    content TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_dataroom_notes_path ON dataroom_notes(file_path);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    created_at TEXT DEFAULT (datetime('now')),
    expires_at TEXT
);

-- Toplu mail geçmişi: her gönderim bir "kampanya", her alıcı bir satır
CREATE TABLE IF NOT EXISTS bulk_campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT DEFAULT (datetime('now')),
    finished_at TEXT,
    account_id INTEGER,
    account_email TEXT,
    filename TEXT,                 -- yüklenen liste dosyasının adı
    subject TEXT,                  -- sabit konu ya da "(sütun: Konu)"
    body_preview TEXT,             -- içeriğin ilk bölümü
    is_html INTEGER DEFAULT 0,
    is_test INTEGER DEFAULT 0,     -- deneme maili mi
    total INTEGER DEFAULT 0,
    sent INTEGER DEFAULT 0,
    failed INTEGER DEFAULT 0,
    skipped INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS bulk_recipients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER,
    email TEXT,
    subject TEXT,                  -- bu alıcıya giden gerçek konu
    status TEXT,                   -- sent | failed | skipped
    error TEXT,
    sent_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_bulk_rcpt_campaign ON bulk_recipients(campaign_id);
CREATE INDEX IF NOT EXISTS idx_bulk_rcpt_email ON bulk_recipients(email);
CREATE INDEX IF NOT EXISTS idx_bulk_camp_started ON bulk_campaigns(started_at DESC);

-- Görevler
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    due_date TEXT,                   -- YYYY-MM-DD (boş olabilir)
    priority TEXT DEFAULT 'orta',    -- dusuk | orta | yuksek | acil
    status TEXT DEFAULT 'yapilacak', -- yapilacak | devam_ediyor | tamamlandi | iptal
    tags TEXT DEFAULT '',            -- virgülle ayrılmış etiketler
    assignee TEXT DEFAULT '',        -- ilgili kişi (ad/e-posta, serbest metin)
    related_email_id INTEGER,
    related_file_path TEXT,
    related_event_id INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due_date);

-- Hatırlatmalar: görevlerden farklı olarak öncelik/etiket/kişi taşımayan,
-- yalnızca metin + zamanı olan hafif bir varlık.
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    remind_at TEXT NOT NULL,         -- ISO tarih-saat
    status TEXT DEFAULT 'bekliyor',  -- bekliyor | tamamlandi | iptal
    related_email_id INTEGER,
    related_file_path TEXT,
    related_event_id INTEGER,
    related_task_id INTEGER,
    notified_at TEXT,                -- e-posta bildirimi gönderildi mi (tek seferlik)
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_reminders_remind_at ON reminders(remind_at);
CREATE INDEX IF NOT EXISTS idx_reminders_status ON reminders(status);

-- Cevap bekliyorum: gönderdiğimiz bir mailin karşılığında yanıt gelene kadar
-- takip edilmesi. Sent klasörü senkronize edilmediği için kayıt gönderim
-- anında burada oluşturulur; çözümleme, gelen bir mailin in_reply_to/refs
-- alanında bu satırın message_id'sinin geçip geçmediğine bakar.
CREATE TABLE IF NOT EXISTS awaiting_replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER,
    to_email TEXT NOT NULL,
    to_name TEXT DEFAULT '',
    subject TEXT DEFAULT '',
    message_id TEXT NOT NULL,        -- gönderdiğimiz mailin ürettiğimiz Message-ID'si
    sent_at TEXT DEFAULT (datetime('now')),
    due_at TEXT NOT NULL,            -- sent_at + kullanıcının seçtiği gün sayısı
    status TEXT DEFAULT 'bekliyor',  -- bekliyor | cevaplandi
    resolved_at TEXT,
    resolved_email_id INTEGER,       -- otomatik eşleşen gelen mail (varsa)
    notified_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_awaiting_status ON awaiting_replies(status);
CREATE INDEX IF NOT EXISTS idx_awaiting_message_id ON awaiting_replies(message_id);
CREATE INDEX IF NOT EXISTS idx_emails_in_reply_to ON emails(in_reply_to);

-- Kalıcı Donna konuşmaları
CREATE TABLE IF NOT EXISTS donna_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT DEFAULT 'Yeni sohbet',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_donna_conv_updated ON donna_conversations(updated_at DESC);

CREATE TABLE IF NOT EXISTS donna_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL,              -- user | assistant
    content TEXT NOT NULL,
    sources TEXT DEFAULT '[]',       -- JSON: kaynak mail listesi (varsa)
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_donna_msg_conv ON donna_messages(conversation_id, id);

-- Donna'nın hatırladığı kullanıcı bilgileri: yalnızca kullanıcı açıkça
-- "bunu hatırla" dediğinde (onay kartı üzerinden) veya elle eklenir; her
-- Donna yanıtının bağlamına dahil edilir.
CREATE TABLE IF NOT EXISTS donna_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    source TEXT DEFAULT 'kullanici_komutu',  -- kullanici_komutu | elle
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_donna_memories_created ON donna_memories(created_at DESC);

CREATE TABLE IF NOT EXISTS auth_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT DEFAULT (datetime('now')),
    ip TEXT,
    user_agent TEXT,
    event TEXT,           -- login_success | login_fail | twofa_fail | lockout | setup | logout | 2fa_enabled | 2fa_disabled
    success INTEGER       -- 1 başarılı, 0 başarısız
);
CREATE INDEX IF NOT EXISTS idx_auth_log_ts ON auth_log(ts DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_emails_msgid_account
    ON emails(message_id, account_id);
CREATE INDEX IF NOT EXISTS idx_emails_category ON emails(category);
CREATE INDEX IF NOT EXISTS idx_emails_status ON emails(status);
"""


@contextmanager
def get_db():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _migrate(db: sqlite3.Connection):
    """Eski şemalardan geçiş."""
    cols = {r["name"] for r in db.execute("PRAGMA table_info(emails)").fetchall()}
    if cols and "account_id" not in cols:
        # tek hesaplı ilk şema → çoklu hesap
        db.execute("ALTER TABLE emails RENAME TO emails_old")
        db.executescript(SCHEMA)
        db.execute(
            """INSERT INTO emails (account_id, message_id, imap_uid, sender_name,
                   sender_email, subject, date, body_text, category, priority,
                   summary, needs_reply, suggested_reply, status, attachments, created_at)
               SELECT NULL, message_id, imap_uid, sender_name, sender_email,
                   subject, date, body_text, category, priority, summary,
                   needs_reply, suggested_reply, status, attachments, created_at
               FROM emails_old"""
        )
        db.execute("DROP TABLE emails_old")
    elif cols and "event_json" not in cols:
        # takvim öncesi şema → event_json sütunu ekle
        db.execute("ALTER TABLE emails ADD COLUMN event_json TEXT")
    if cols and "is_read" not in cols:
        # posta v2 öncesi şema → okundu/yıldız/erteleme sütunları
        db.execute("ALTER TABLE emails ADD COLUMN is_read INTEGER DEFAULT 0")
        db.execute("ALTER TABLE emails ADD COLUMN starred INTEGER DEFAULT 0")
        db.execute("ALTER TABLE emails ADD COLUMN snooze_until TEXT")
        db.execute("UPDATE emails SET is_read = 1")  # mevcut mailler okunmuş sayılsın
    acc_cols = {r["name"] for r in db.execute("PRAGMA table_info(accounts)").fetchall()}
    if acc_cols and "auth_type" not in acc_cols:
        # OAuth öncesi şema → kimlik doğrulama türü sütunu
        db.execute("ALTER TABLE accounts ADD COLUMN auth_type TEXT DEFAULT 'password'")
    if cols and "thread_id" not in cols:
        # threading öncesi şema → konuşma sütunları; mevcut mailler tek başına dizi olur
        db.execute("ALTER TABLE emails ADD COLUMN in_reply_to TEXT")
        db.execute("ALTER TABLE emails ADD COLUMN refs TEXT")
        db.execute("ALTER TABLE emails ADD COLUMN thread_id TEXT")
        db.execute("UPDATE emails SET thread_id = message_id WHERE thread_id IS NULL")
    meta_cols = {r["name"] for r in db.execute("PRAGMA table_info(dataroom_meta)").fetchall()}
    if meta_cols and "tags" not in meta_cols:
        # dataroom v2 öncesi şema → yeni sütunlar
        for stmt in (
            "ALTER TABLE dataroom_meta ADD COLUMN tags TEXT",
            "ALTER TABLE dataroom_meta ADD COLUMN favorite INTEGER DEFAULT 0",
            "ALTER TABLE dataroom_meta ADD COLUMN share_expires TEXT",
            "ALTER TABLE dataroom_meta ADD COLUMN share_downloads INTEGER DEFAULT 0",
        ):
            db.execute(stmt)
    if meta_cols and "doc_type" not in meta_cols:
        # içerik arama / AI analiz öncesi şema → belge analizi sütunları
        for stmt in (
            "ALTER TABLE dataroom_meta ADD COLUMN doc_type TEXT",
            "ALTER TABLE dataroom_meta ADD COLUMN doc_date TEXT",
            "ALTER TABLE dataroom_meta ADD COLUMN doc_amount TEXT",
            "ALTER TABLE dataroom_meta ADD COLUMN ai_summary TEXT",
        ):
            db.execute(stmt)


FTS_AVAILABLE = False


def init_db():
    global FTS_AVAILABLE
    with get_db() as db:
        _migrate(db)
        db.executescript(SCHEMA)
        try:
            db.execute(
                """CREATE VIRTUAL TABLE IF NOT EXISTS dataroom_fts
                   USING fts5(path UNINDEXED, content,
                              tokenize='unicode61 remove_diacritics 2')"""
            )
            db.execute(
                """CREATE VIRTUAL TABLE IF NOT EXISTS emails_fts
                   USING fts5(email_id UNINDEXED, sender, subject, summary, body,
                              tokenize='unicode61 remove_diacritics 2')"""
            )
            FTS_AVAILABLE = True
            # Geriye dönük doldurma: FTS boş ama mail varsa dizinle
            n_fts = db.execute("SELECT COUNT(*) AS n FROM emails_fts").fetchone()["n"]
            if n_fts == 0:
                db.execute(
                    """INSERT INTO emails_fts (email_id, sender, subject, summary, body)
                       SELECT id, COALESCE(sender_name,'') || ' ' || COALESCE(sender_email,''),
                              COALESCE(subject,''), COALESCE(summary,''),
                              substr(COALESCE(body_text,''), 1, 20000)
                       FROM emails"""
                )
        except sqlite3.OperationalError:
            FTS_AVAILABLE = False  # FTS5 yoksa LIKE aramasına düşülür
        _encrypt_legacy_secrets(db)


def _encrypt_legacy_secrets(db: sqlite3.Connection):
    """Düz metin saklanmış eski hesap/takvim şifrelerini şifreler (tek seferlik)."""
    for table in ("accounts", "calendars"):
        rows = db.execute(f"SELECT id, password FROM {table} WHERE password != ''").fetchall()
        for r in rows:
            if r["password"] and not crypto.is_encrypted(r["password"]):
                db.execute(f"UPDATE {table} SET password = ? WHERE id = ?",
                           (crypto.encrypt_secret(r["password"]), r["id"]))


# ---- Ayarlar + Oturumlar (giriş sistemi) ----

def get_setting(key: str) -> str | None:
    with get_db() as db:
        row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None


def set_setting(key: str, value: str):
    with get_db() as db:
        db.execute(
            """INSERT INTO settings (key, value) VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
            (key, value),
        )


def delete_setting(key: str):
    with get_db() as db:
        db.execute("DELETE FROM settings WHERE key = ?", (key,))


def create_session(token: str, days: int):
    with get_db() as db:
        db.execute(
            """INSERT INTO sessions (token, expires_at)
               VALUES (?, datetime('now', ?))""",
            (token, f"+{days} days"),
        )
        db.execute("DELETE FROM sessions WHERE expires_at < datetime('now')")


def touch_session(token: str, days: int) -> bool:
    """Oturum geçerliyse süresini uzatır ve True döner."""
    with get_db() as db:
        row = db.execute(
            "SELECT 1 FROM sessions WHERE token = ? AND expires_at > datetime('now')",
            (token,),
        ).fetchone()
        if not row:
            return False
        db.execute(
            "UPDATE sessions SET expires_at = datetime('now', ?) WHERE token = ?",
            (f"+{days} days", token),
        )
        return True


def delete_session(token: str):
    with get_db() as db:
        db.execute("DELETE FROM sessions WHERE token = ?", (token,))


# ---- Toplu mail geçmişi ----

def create_campaign(data: dict) -> int:
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO bulk_campaigns
               (account_id, account_email, filename, subject, body_preview,
                is_html, is_test, total)
               VALUES (?,?,?,?,?,?,?,?)""",
            (data.get("account_id"), data.get("account_email", ""),
             data.get("filename", ""), data.get("subject", ""),
             (data.get("body_preview") or "")[:400],
             1 if data.get("is_html") else 0,
             1 if data.get("is_test") else 0,
             data.get("total", 0)),
        )
        return cur.lastrowid


def add_bulk_recipient(campaign_id: int, email: str, subject: str,
                       status: str, error: str = ""):
    with get_db() as db:
        db.execute(
            """INSERT INTO bulk_recipients (campaign_id, email, subject, status, error)
               VALUES (?,?,?,?,?)""",
            (campaign_id, email[:200], (subject or "")[:300], status, (error or "")[:300]),
        )


def finish_campaign(campaign_id: int, sent: int, failed: int, skipped: int):
    with get_db() as db:
        db.execute(
            """UPDATE bulk_campaigns
               SET finished_at = datetime('now'), sent = ?, failed = ?, skipped = ?
               WHERE id = ?""",
            (sent, failed, skipped, campaign_id),
        )


def list_campaigns(limit: int = 50) -> list[dict]:
    with get_db() as db:
        rows = db.execute(
            """SELECT * FROM bulk_campaigns ORDER BY id DESC LIMIT ?""", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_campaign(campaign_id: int) -> dict | None:
    with get_db() as db:
        row = db.execute("SELECT * FROM bulk_campaigns WHERE id = ?", (campaign_id,)).fetchone()
        return dict(row) if row else None


def list_campaign_recipients(campaign_id: int, limit: int = 5000) -> list[dict]:
    with get_db() as db:
        rows = db.execute(
            """SELECT email, subject, status, error, sent_at FROM bulk_recipients
               WHERE campaign_id = ? ORDER BY id LIMIT ?""",
            (campaign_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def search_bulk_recipients(q: str, limit: int = 200) -> list[dict]:
    """Gönderilmiş maillerde ara: alıcı adresi veya konu."""
    like = f"%{(q or '').strip()}%"
    with get_db() as db:
        rows = db.execute(
            """SELECT r.email, r.subject, r.status, r.error, r.sent_at,
                      c.id AS campaign_id, c.account_email, c.filename, c.is_test
               FROM bulk_recipients r
               JOIN bulk_campaigns c ON c.id = r.campaign_id
               WHERE r.email LIKE ? OR r.subject LIKE ?
               ORDER BY r.id DESC LIMIT ?""",
            (like, like, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def bulk_stats() -> dict:
    with get_db() as db:
        row = db.execute(
            """SELECT COUNT(*) AS campaigns,
                      COALESCE(SUM(sent), 0) AS sent,
                      COALESCE(SUM(failed), 0) AS failed
               FROM bulk_campaigns WHERE is_test = 0"""
        ).fetchone()
        uniq = db.execute(
            "SELECT COUNT(DISTINCT email) AS n FROM bulk_recipients WHERE status = 'sent'"
        ).fetchone()
        out = dict(row)
        out["unique_recipients"] = uniq["n"]
        return out


# ---- Giriş / güvenlik günlüğü ----

def add_auth_log(ip: str, user_agent: str, event: str, success: bool):
    with get_db() as db:
        db.execute(
            "INSERT INTO auth_log (ip, user_agent, event, success) VALUES (?,?,?,?)",
            (ip, (user_agent or "")[:300], event, 1 if success else 0),
        )
        # Günlüğü makul tut: en yeni 2000 kaydı sakla
        db.execute(
            """DELETE FROM auth_log WHERE id NOT IN
               (SELECT id FROM auth_log ORDER BY id DESC LIMIT 2000)"""
        )


def list_auth_log(limit: int = 100) -> list[dict]:
    with get_db() as db:
        rows = db.execute(
            "SELECT ts, ip, user_agent, event, success FROM auth_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


# ---- Hesaplar ----

def create_account(data: dict) -> int:
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO accounts
               (display_name, email, password, imap_host, imap_port,
                smtp_host, smtp_port, smtp_security, auth_type)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                data.get("display_name") or data["email"],
                data["email"],
                crypto.encrypt_secret(data["password"]),
                data["imap_host"],
                data.get("imap_port", 993),
                data["smtp_host"],
                data.get("smtp_port", 465),
                data.get("smtp_security", "ssl"),
                data.get("auth_type", "password"),
            ),
        )
        return cur.lastrowid


def update_account_secret(account_id: int, secret: str):
    """OAuth jeton önbelleği yenilenince şifreli olarak günceller."""
    with get_db() as db:
        db.execute("UPDATE accounts SET password = ? WHERE id = ?",
                   (crypto.encrypt_secret(secret), account_id))


def list_accounts(include_password: bool = False) -> list[dict]:
    with get_db() as db:
        rows = db.execute("SELECT * FROM accounts ORDER BY id").fetchall()
        accounts = [dict(r) for r in rows]
        for a in accounts:
            if include_password:
                a["password"] = crypto.decrypt_secret(a.get("password") or "")
            else:
                a.pop("password", None)
        return accounts


def get_account(account_id: int) -> dict | None:
    with get_db() as db:
        row = db.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        if not row:
            return None
        account = dict(row)
        account["password"] = crypto.decrypt_secret(account.get("password") or "")
        return account


def get_account_by_email(email_addr: str) -> dict | None:
    with get_db() as db:
        row = db.execute("SELECT * FROM accounts WHERE email = ?", (email_addr,)).fetchone()
        if not row:
            return None
        account = dict(row)
        account["password"] = crypto.decrypt_secret(account.get("password") or "")
        return account


def delete_account(account_id: int):
    with get_db() as db:
        db.execute("DELETE FROM accounts WHERE id = ?", (account_id,))


# ---- Takvimler ----

CALENDAR_COLORS = ["#0f8a6d", "#2563eb", "#d64550", "#b06d0a", "#7c3aed", "#0e7490", "#be5a0e"]


def create_calendar(data: dict) -> int:
    with get_db() as db:
        n = db.execute("SELECT COUNT(*) AS n FROM calendars").fetchone()["n"]
        cur = db.execute(
            """INSERT INTO calendars (name, type, url, username, password, color)
               VALUES (?,?,?,?,?,?)""",
            (
                data["name"],
                data["type"],
                data.get("url", ""),
                data.get("username", ""),
                crypto.encrypt_secret(data.get("password", "")),
                data.get("color") or CALENDAR_COLORS[n % len(CALENDAR_COLORS)],
            ),
        )
        return cur.lastrowid


def list_calendars(include_password: bool = False) -> list[dict]:
    with get_db() as db:
        rows = db.execute("SELECT * FROM calendars ORDER BY id").fetchall()
        cals = [dict(r) for r in rows]
        for c in cals:
            if include_password:
                c["password"] = crypto.decrypt_secret(c.get("password") or "")
            else:
                c.pop("password", None)
                c.pop("username", None)
                c.pop("url", None)
        return cals


def get_calendar(calendar_id: int) -> dict | None:
    with get_db() as db:
        row = db.execute("SELECT * FROM calendars WHERE id = ?", (calendar_id,)).fetchone()
        if not row:
            return None
        cal = dict(row)
        cal["password"] = crypto.decrypt_secret(cal.get("password") or "")
        return cal


def delete_calendar(calendar_id: int):
    with get_db() as db:
        db.execute("DELETE FROM events WHERE calendar_id = ?", (calendar_id,))
        db.execute("DELETE FROM calendars WHERE id = ?", (calendar_id,))


# ---- Etkinlikler ----

def replace_synced_events(calendar_id: int, events: list[dict]):
    """Bir takvimin harici (sync) etkinliklerini yenileriyle değiştirir."""
    with get_db() as db:
        db.execute(
            "DELETE FROM events WHERE calendar_id = ? AND source = 'sync'", (calendar_id,)
        )
        for ev in events:
            db.execute(
                """INSERT INTO events (calendar_id, uid, title, start, end, all_day,
                                       location, notes, source)
                   VALUES (?,?,?,?,?,?,?,?,'sync')""",
                (
                    calendar_id,
                    ev.get("uid"),
                    ev.get("title"),
                    ev.get("start"),
                    ev.get("end"),
                    1 if ev.get("all_day") else 0,
                    ev.get("location"),
                    ev.get("notes"),
                ),
            )


def insert_event(data: dict) -> int:
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO events (calendar_id, uid, title, start, end, all_day,
                                   location, notes, source, source_email_id)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                data.get("calendar_id"),
                data.get("uid"),
                data.get("title"),
                data.get("start"),
                data.get("end"),
                1 if data.get("all_day") else 0,
                data.get("location"),
                data.get("notes"),
                data.get("source", "manual"),
                data.get("source_email_id"),
            ),
        )
        return cur.lastrowid


def list_events(start: str, end: str) -> list[dict]:
    with get_db() as db:
        rows = db.execute(
            """SELECT e.*, c.name AS calendar_name, c.color AS calendar_color,
                      c.type AS calendar_type
               FROM events e LEFT JOIN calendars c ON c.id = e.calendar_id
               WHERE e.start < ? AND (e.end >= ? OR e.start >= ?)
               ORDER BY e.start""",
            (end, start, start),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["all_day"] = bool(d["all_day"])
            out.append(d)
        return out


def update_event(event_id: int, **fields):
    """Etkinliğin verilen alanlarını günceller."""
    allowed = {"title", "start", "end", "all_day", "location", "notes", "calendar_id"}
    sets, values = [], []
    for key, val in fields.items():
        if key in allowed:
            sets.append(f"{key} = ?")
            values.append(val)
    if not sets:
        return
    values.append(event_id)
    with get_db() as db:
        db.execute(f"UPDATE events SET {', '.join(sets)} WHERE id = ?", values)


def delete_event(event_id: int):
    with get_db() as db:
        db.execute("DELETE FROM events WHERE id = ?", (event_id,))


def get_event(event_id: int) -> dict | None:
    with get_db() as db:
        row = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        return dict(row) if row else None


# ---- Dataroom meta (not, etiket, favori, paylaşım) ----

def all_file_meta() -> dict:
    """path → meta eşlemesi."""
    with get_db() as db:
        rows = db.execute(
            """SELECT path, note, tags, favorite, share_token, share_expires,
                      share_downloads, doc_type, doc_date, doc_amount, ai_summary
               FROM dataroom_meta"""
        ).fetchall()
        return {
            r["path"]: {
                "note": r["note"],
                "tags": r["tags"],
                "favorite": bool(r["favorite"]),
                "share_token": r["share_token"],
                "share_expires": r["share_expires"],
                "share_downloads": r["share_downloads"] or 0,
                "doc_type": r["doc_type"],
                "doc_date": r["doc_date"],
                "doc_amount": r["doc_amount"],
                "ai_summary": r["ai_summary"],
            }
            for r in rows
        }


def _meta_upsert(path: str, column: str, value):
    with get_db() as db:
        db.execute(
            f"""INSERT INTO dataroom_meta (path, {column}) VALUES (?, ?)
                ON CONFLICT(path) DO UPDATE SET {column} = excluded.{column}""",
            (path, value),
        )


def set_file_note(path: str, note: str):
    _meta_upsert(path, "note", note)


def set_file_tags(path: str, tags: str):
    _meta_upsert(path, "tags", tags)


def set_favorite(path: str, favorite: bool):
    _meta_upsert(path, "favorite", 1 if favorite else 0)


def set_share_token(path: str, token: str, expires: str | None = None):
    with get_db() as db:
        db.execute(
            """INSERT INTO dataroom_meta (path, share_token, share_expires, share_downloads)
               VALUES (?, ?, ?, 0)
               ON CONFLICT(path) DO UPDATE SET
                   share_token = excluded.share_token,
                   share_expires = excluded.share_expires,
                   share_downloads = 0""",
            (path, token, expires),
        )


def get_share_info(path: str) -> dict | None:
    with get_db() as db:
        row = db.execute(
            """SELECT share_token, share_expires, share_downloads
               FROM dataroom_meta WHERE path = ?""",
            (path,),
        ).fetchone()
        return dict(row) if row else None


def clear_share_token(path: str):
    with get_db() as db:
        db.execute(
            "UPDATE dataroom_meta SET share_token = NULL, share_expires = NULL WHERE path = ?",
            (path,),
        )


def get_share_by_token(token: str) -> dict | None:
    with get_db() as db:
        row = db.execute(
            "SELECT path, share_expires FROM dataroom_meta WHERE share_token = ?", (token,)
        ).fetchone()
        return dict(row) if row else None


def increment_share_downloads(path: str):
    with get_db() as db:
        db.execute(
            "UPDATE dataroom_meta SET share_downloads = COALESCE(share_downloads, 0) + 1 WHERE path = ?",
            (path,),
        )


def update_meta_path(old_path: str, new_path: str):
    with get_db() as db:
        db.execute("UPDATE dataroom_meta SET path = ? WHERE path = ?", (new_path, old_path))


def delete_file_meta(path: str):
    with get_db() as db:
        db.execute("DELETE FROM dataroom_meta WHERE path = ?", (path,))


# ---- Dataroom içerik dizini (metin çıkarma + içerik arama) ----

def get_text_mtime(path: str) -> float | None:
    with get_db() as db:
        row = db.execute("SELECT mtime FROM dataroom_text WHERE path = ?", (path,)).fetchone()
        return row["mtime"] if row else None


def upsert_file_text(path: str, content: str, mtime: float):
    with get_db() as db:
        db.execute(
            """INSERT INTO dataroom_text (path, content, mtime, extracted_at)
               VALUES (?, ?, ?, datetime('now'))
               ON CONFLICT(path) DO UPDATE SET
                   content = excluded.content, mtime = excluded.mtime,
                   extracted_at = excluded.extracted_at""",
            (path, content, mtime),
        )
        if FTS_AVAILABLE:
            db.execute("DELETE FROM dataroom_fts WHERE path = ?", (path,))
            if content:
                db.execute("INSERT INTO dataroom_fts (path, content) VALUES (?, ?)",
                           (path, content))


def get_file_text(path: str) -> str:
    with get_db() as db:
        row = db.execute("SELECT content FROM dataroom_text WHERE path = ?", (path,)).fetchone()
        return (row["content"] or "") if row else ""


def delete_file_text(path: str):
    with get_db() as db:
        db.execute("DELETE FROM dataroom_text WHERE path = ?", (path,))
        if FTS_AVAILABLE:
            db.execute("DELETE FROM dataroom_fts WHERE path = ?", (path,))


def update_text_path(old_path: str, new_path: str):
    with get_db() as db:
        db.execute("UPDATE dataroom_text SET path = ? WHERE path = ?", (new_path, old_path))
        if FTS_AVAILABLE:
            row = db.execute("SELECT content FROM dataroom_text WHERE path = ?",
                             (new_path,)).fetchone()
            db.execute("DELETE FROM dataroom_fts WHERE path = ?", (old_path,))
            if row and row["content"]:
                db.execute("INSERT INTO dataroom_fts (path, content) VALUES (?, ?)",
                           (new_path, row["content"]))


def search_file_contents(q: str, limit: int = 50) -> list[dict]:
    """Dosya içeriklerinde arama; [{path, snippet}] döner. Eşleşme [[..]] ile işaretli."""
    tokens = re.findall(r"\w+", q, re.UNICODE)[:8]
    if not tokens:
        return []
    with get_db() as db:
        if FTS_AVAILABLE:
            match = " ".join(f'"{t}"*' for t in tokens)  # önek araması, TR karakter güvenli
            try:
                rows = db.execute(
                    """SELECT path, snippet(dataroom_fts, 1, '[[', ']]', ' … ', 10) AS snip
                       FROM dataroom_fts WHERE dataroom_fts MATCH ? LIMIT ?""",
                    (match, limit),
                ).fetchall()
                return [{"path": r["path"], "snippet": r["snip"]} for r in rows]
            except sqlite3.OperationalError:
                pass  # sorgu FTS'i kızdırırsa LIKE'a düş
        results = []
        rows = db.execute("SELECT path, content FROM dataroom_text WHERE content != ''").fetchall()
        low_tokens = [t.lower() for t in tokens]
        for r in rows:
            content_low = (r["content"] or "").lower()
            positions = [content_low.find(t) for t in low_tokens]
            if any(p < 0 for p in positions):
                continue
            first = min(positions)
            start = max(0, first - 60)
            snip = r["content"][start:first + 90].replace("\n", " ")
            results.append({"path": r["path"], "snippet": " … " + snip + " … "})
            if len(results) >= limit:
                break
        return results


def set_doc_analysis(path: str, doc_type: str, doc_date: str,
                     doc_amount: str, ai_summary: str):
    with get_db() as db:
        db.execute(
            """INSERT INTO dataroom_meta (path, doc_type, doc_date, doc_amount, ai_summary)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(path) DO UPDATE SET
                   doc_type = excluded.doc_type, doc_date = excluded.doc_date,
                   doc_amount = excluded.doc_amount, ai_summary = excluded.ai_summary""",
            (path, doc_type, doc_date, doc_amount, ai_summary),
        )


# ---- Dataroom etkinlik günlüğü ----

def log_activity(action: str, path: str, detail: str = ""):
    with get_db() as db:
        db.execute(
            "INSERT INTO dataroom_activity (action, path, detail) VALUES (?, ?, ?)",
            (action, path, detail),
        )


def list_activity(limit: int = 25) -> list[dict]:
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM dataroom_activity ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


# ---- Mailler ----

def email_exists(message_id: str, account_id: int | None) -> bool:
    with get_db() as db:
        row = db.execute(
            "SELECT 1 FROM emails WHERE message_id = ? AND account_id IS ?",
            (message_id, account_id),
        ).fetchone()
        return row is not None


def _compute_thread_id(db: sqlite3.Connection, data: dict) -> str:
    """Konuşma anahtarı: zincirdeki bilinen bir mailin thread'i, yoksa kök Message-ID.

    References başlığı kökten ebeveyne doğru tüm zinciri taşır; ilk halka kök
    kabul edilir. Kökü olmayan (yeni başlayan) mailin anahtarı kendi ID'sidir.
    """
    refs = (data.get("references") or "").split()
    candidates = refs + ([data["in_reply_to"]] if data.get("in_reply_to") else [])
    if not candidates:
        return data["message_id"]
    placeholders = ",".join("?" for _ in candidates)
    row = db.execute(
        f"""SELECT thread_id FROM emails
            WHERE account_id IS ? AND thread_id IS NOT NULL
              AND message_id IN ({placeholders}) LIMIT 1""",
        (data.get("account_id"), *candidates),
    ).fetchone()
    return row["thread_id"] if row else candidates[0]


def insert_email(data: dict) -> int:
    with get_db() as db:
        thread_id = _compute_thread_id(db, data)
        cur = db.execute(
            """INSERT INTO emails
               (account_id, message_id, imap_uid, sender_name, sender_email,
                subject, date, body_text, category, priority, summary,
                needs_reply, suggested_reply, attachments, event_json,
                in_reply_to, refs, thread_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                data.get("account_id"),
                data["message_id"],
                data.get("imap_uid"),
                data.get("sender_name"),
                data.get("sender_email"),
                data.get("subject"),
                data.get("date"),
                data.get("body_text"),
                data.get("category"),
                data.get("priority"),
                data.get("summary"),
                1 if data.get("needs_reply") else 0,
                data.get("suggested_reply"),
                json.dumps(data.get("attachments", []), ensure_ascii=False),
                data.get("event_json"),
                data.get("in_reply_to"),
                data.get("references"),
                thread_id,
            ),
        )
        if FTS_AVAILABLE:
            db.execute(
                """INSERT INTO emails_fts (email_id, sender, subject, summary, body)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    cur.lastrowid,
                    f"{data.get('sender_name') or ''} {data.get('sender_email') or ''}",
                    data.get("subject") or "",
                    data.get("summary") or "",
                    (data.get("body_text") or "")[:20000],
                ),
            )
        return cur.lastrowid


def _view_conditions(view: str) -> tuple[list[str], list]:
    """Görünüm sekmeleri: inbox | starred | awaiting | snoozed | archived."""
    now = __import__("datetime").datetime.now().isoformat(timespec="minutes")
    if view == "starred":
        return ["e.starred = 1", "e.status != 'archived'"], []
    if view == "awaiting":
        return ["e.needs_reply = 1", "e.status = 'new'",
                "(e.snooze_until IS NULL OR e.snooze_until <= ?)"], [now]
    if view == "snoozed":
        return ["e.snooze_until > ?", "e.status != 'archived'"], [now]
    if view == "archived":
        return ["e.status = 'archived'"], []
    # inbox (varsayılan): arşivlenmemiş + ertelenmemiş
    return ["e.status != 'archived'",
            "(e.snooze_until IS NULL OR e.snooze_until <= ?)"], [now]


def list_emails(category: str | None = None, status: str | None = None,
                account_id: int | None = None, view: str = "inbox") -> list[dict]:
    query = """SELECT e.*, a.email AS account_email, a.display_name AS account_name
               FROM emails e LEFT JOIN accounts a ON a.id = e.account_id"""
    conditions, params = _view_conditions(view)
    if category:
        conditions.append("e.category = ?")
        params.append(category)
    if status:
        conditions.append("e.status = ?")
        params.append(status)
    if account_id:
        conditions.append("e.account_id = ?")
        params.append(account_id)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY e.date DESC, e.id DESC"
    with get_db() as db:
        rows = db.execute(query, params).fetchall()
        return [_row_to_dict(r) for r in rows]


def list_threads(category: str | None = None, status: str | None = None,
                 account_id: int | None = None, view: str = "inbox") -> list[dict]:
    """Görünüme uyan mailleri konuşma dizilerine gruplar.

    Her dizi için en yeni mail temsilci olur; thread_count ve thread_unread
    dizinin tamamı (filtreden bağımsız, arşiv hariç) üzerinden hesaplanır.
    """
    emails = list_emails(category=category, status=status,
                         account_id=account_id, view=view)
    with get_db() as db:
        stats = {
            (r["account_id"], r["thread_id"]): (r["n"], r["unread"])
            for r in db.execute(
                """SELECT account_id, thread_id, COUNT(*) AS n,
                          SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END) AS unread
                   FROM emails WHERE status != 'archived'
                   GROUP BY account_id, thread_id"""
            ).fetchall()
        }
    threads, seen = [], set()
    for e in emails:  # tarih DESC sıralı → ilk görülen temsilcidir
        key = (e["account_id"], e["thread_id"])
        if key in seen:
            continue
        seen.add(key)
        n, unread = stats.get(key, (1, 0 if e["is_read"] else 1))
        e["thread_count"] = n
        e["thread_unread"] = unread
        threads.append(e)
    return threads


def get_thread(thread_id: str, account_id: int | None) -> list[dict]:
    """Dizinin tüm mailleri, eskiden yeniye."""
    with get_db() as db:
        rows = db.execute(
            """SELECT e.*, a.email AS account_email, a.display_name AS account_name
               FROM emails e LEFT JOIN accounts a ON a.id = e.account_id
               WHERE e.thread_id = ? AND e.account_id IS ?
               ORDER BY e.date ASC, e.id ASC""",
            (thread_id, account_id),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


def mark_thread_read(thread_id: str, account_id: int | None):
    with get_db() as db:
        db.execute(
            "UPDATE emails SET is_read = 1 WHERE thread_id = ? AND account_id IS ?",
            (thread_id, account_id),
        )


def search_emails_for_chat(question: str, limit: int = 12) -> list[dict]:
    """Soruyla ilgili mailleri bulur (AI sohbeti için bağlam).

    FTS eşleşmeleri (bm25 sıralı) + her durumda en yeni birkaç mail; böylece
    "son gelen mail ne?" gibi anahtar kelimesiz sorular da bağlam bulur.
    """
    tokens = re.findall(r"\w{2,}", question, re.UNICODE)[:10]
    ids: list[int] = []
    with get_db() as db:
        if FTS_AVAILABLE and tokens:
            # Kesişim yerine herhangi-biri (OR): sorudaki gereksiz kelimeler
            # ("acaba", "neydi") eşleşmeyi tamamen boşa düşürmesin
            match = " OR ".join(f'"{t}"*' for t in tokens)
            try:
                rows = db.execute(
                    """SELECT email_id FROM emails_fts
                       WHERE emails_fts MATCH ? ORDER BY bm25(emails_fts) LIMIT ?""",
                    (match, limit),
                ).fetchall()
                ids = [r["email_id"] for r in rows]
            except sqlite3.OperationalError:
                ids = []
        if not ids and tokens:
            like = f"%{tokens[0]}%"
            rows = db.execute(
                """SELECT id FROM emails
                   WHERE subject LIKE ? OR body_text LIKE ? OR sender_name LIKE ?
                   ORDER BY date DESC LIMIT ?""",
                (like, like, like, limit),
            ).fetchall()
            ids = [r["id"] for r in rows]
        # En yeni mailleri her zaman ekle (tekrarsız)
        recent = db.execute(
            "SELECT id FROM emails ORDER BY date DESC, id DESC LIMIT 5"
        ).fetchall()
        for r in recent:
            if r["id"] not in ids:
                ids.append(r["id"])
        ids = ids[: limit + 5]
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        rows = db.execute(
            f"""SELECT e.*, a.email AS account_email, a.display_name AS account_name
                FROM emails e LEFT JOIN accounts a ON a.id = e.account_id
                WHERE e.id IN ({placeholders})""",
            ids,
        ).fetchall()
        by_id = {r["id"]: _row_to_dict(r) for r in rows}
        return [by_id[i] for i in ids if i in by_id]


def global_search(q: str) -> dict:
    """Tek sorguda mail + dosya + etkinlik araması (Cmd+K paleti)."""
    tokens = re.findall(r"\w{2,}", q, re.UNICODE)[:8]
    out = {"emails": [], "files": [], "events": []}
    if not tokens:
        return out
    like = f"%{q.strip()}%"
    with get_db() as db:
        if FTS_AVAILABLE:
            match = " OR ".join(f'"{t}"*' for t in tokens)
            try:
                rows = db.execute(
                    """SELECT email_id, snippet(emails_fts, -1, '[[', ']]', ' … ', 10) AS snip
                       FROM emails_fts WHERE emails_fts MATCH ?
                       ORDER BY bm25(emails_fts) LIMIT 8""",
                    (match,),
                ).fetchall()
                ids = [r["email_id"] for r in rows]
                snips = {r["email_id"]: r["snip"] for r in rows}
                if ids:
                    ph = ",".join("?" for _ in ids)
                    erows = db.execute(
                        f"""SELECT id, subject, sender_name, sender_email, date
                            FROM emails WHERE id IN ({ph})""", ids).fetchall()
                    by_id = {r["id"]: r for r in erows}
                    out["emails"] = [
                        {"id": i, "subject": by_id[i]["subject"],
                         "sender": by_id[i]["sender_name"] or by_id[i]["sender_email"],
                         "date": by_id[i]["date"], "snippet": snips[i]}
                        for i in ids if i in by_id
                    ]
            except sqlite3.OperationalError:
                pass
            try:
                rows = db.execute(
                    """SELECT path, snippet(dataroom_fts, 1, '[[', ']]', ' … ', 10) AS snip
                       FROM dataroom_fts WHERE dataroom_fts MATCH ?
                       ORDER BY bm25(dataroom_fts) LIMIT 6""",
                    (match,),
                ).fetchall()
                out["files"] = [{"path": r["path"], "snippet": r["snip"]} for r in rows]
            except sqlite3.OperationalError:
                pass
        else:
            rows = db.execute(
                """SELECT id, subject, sender_name, sender_email, date FROM emails
                   WHERE subject LIKE ? OR body_text LIKE ? OR sender_name LIKE ?
                   ORDER BY date DESC LIMIT 8""",
                (like, like, like),
            ).fetchall()
            out["emails"] = [
                {"id": r["id"], "subject": r["subject"],
                 "sender": r["sender_name"] or r["sender_email"],
                 "date": r["date"], "snippet": ""}
                for r in rows
            ]
        rows = db.execute(
            """SELECT e.id, e.title, e.start, e.all_day, e.location,
                      c.name AS calendar_name, c.color AS calendar_color
               FROM events e LEFT JOIN calendars c ON c.id = e.calendar_id
               WHERE e.title LIKE ? OR e.location LIKE ? OR e.notes LIKE ?
               ORDER BY e.start DESC LIMIT 5""",
            (like, like, like),
        ).fetchall()
        out["events"] = [dict(r) for r in rows]
    return out


def view_counts(account_id: int | None = None) -> dict:
    """Her görünüm sekmesi için mail sayısı + okunmamış sayısı."""
    counts = {}
    for view in ("inbox", "starred", "awaiting", "snoozed", "archived"):
        conditions, params = _view_conditions(view)
        if account_id:
            conditions.append("e.account_id = ?")
            params.append(account_id)
        query = "SELECT COUNT(*) AS n FROM emails e WHERE " + " AND ".join(conditions)
        with get_db() as db:
            counts[view] = db.execute(query, params).fetchone()["n"]
    conditions, params = _view_conditions("inbox")
    conditions.append("e.is_read = 0")
    if account_id:
        conditions.append("e.account_id = ?")
        params.append(account_id)
    with get_db() as db:
        counts["unread"] = db.execute(
            "SELECT COUNT(*) AS n FROM emails e WHERE " + " AND ".join(conditions), params
        ).fetchone()["n"]
    return counts


def attention_emails(limit: int = 15) -> list[dict]:
    """Donna için: yanıt bekleyen / yüksek öncelikli, arşivlenmemiş mailler."""
    with get_db() as db:
        rows = db.execute(
            """SELECT id, sender_name, sender_email, subject, date, category, priority,
                      summary, needs_reply, is_read, starred, status, event_json
               FROM emails
               WHERE status != 'archived'
                 AND (snooze_until IS NULL OR snooze_until <= datetime('now'))
                 AND (needs_reply = 1 OR priority = 'yüksek' OR is_read = 0)
               ORDER BY CASE priority WHEN 'yüksek' THEN 0 WHEN 'orta' THEN 1 ELSE 2 END,
                        needs_reply DESC, date DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def upcoming_invoices(limit: int = 10) -> list[dict]:
    """Donna için: dataroom'da AI'nın fatura olarak işaretlediği, tarihli belgeler."""
    with get_db() as db:
        rows = db.execute(
            """SELECT path, doc_type, doc_date, doc_amount, ai_summary
               FROM dataroom_meta
               WHERE doc_type IN ('Fatura', 'Dekont/Makbuz')
                 AND doc_date IS NOT NULL AND doc_date != ''
               ORDER BY doc_date DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def recent_documents(limit: int = 8) -> list[dict]:
    """Donna için: dataroom'a en son eklenen/analiz edilen belgeler."""
    with get_db() as db:
        rows = db.execute(
            """SELECT path, doc_type, doc_date, doc_amount, ai_summary, tags
               FROM dataroom_meta
               WHERE doc_type IS NOT NULL AND doc_type != ''
               ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_email(email_id: int) -> dict | None:
    with get_db() as db:
        row = db.execute(
            """SELECT e.*, a.email AS account_email, a.display_name AS account_name
               FROM emails e LEFT JOIN accounts a ON a.id = e.account_id
               WHERE e.id = ?""",
            (email_id,),
        ).fetchone()
        return _row_to_dict(row) if row else None


def update_email(email_id: int, **fields):
    if not fields:
        return
    if "attachments" in fields and not isinstance(fields["attachments"], str):
        fields["attachments"] = json.dumps(fields["attachments"], ensure_ascii=False)
    sets = ", ".join(f"{k} = ?" for k in fields)
    with get_db() as db:
        db.execute(
            f"UPDATE emails SET {sets} WHERE id = ?", (*fields.values(), email_id)
        )


def category_counts(account_id: int | None = None) -> dict:
    query = "SELECT category, COUNT(*) AS n FROM emails"
    params = []
    if account_id:
        query += " WHERE account_id = ?"
        params.append(account_id)
    query += " GROUP BY category"
    with get_db() as db:
        rows = db.execute(query, params).fetchall()
        return {r["category"]: r["n"] for r in rows}


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["attachments"] = json.loads(d.get("attachments") or "[]")
    d["needs_reply"] = bool(d.get("needs_reply"))
    d["is_read"] = bool(d.get("is_read"))
    d["starred"] = bool(d.get("starred"))
    try:
        d["event"] = json.loads(d["event_json"]) if d.get("event_json") else None
    except Exception:
        d["event"] = None
    d.pop("event_json", None)
    return d


# ---- Dataroom Notes (Multiple) ----

def get_file_notes(file_path: str):
    """Dosyaya ait tüm notları getirir."""
    with get_db() as db:
        rows = db.execute(
            "SELECT id, author, content, created_at FROM dataroom_notes WHERE file_path = ? ORDER BY created_at DESC",
            (file_path,),
        ).fetchall()
        return [dict(r) for r in rows]


def add_file_note(file_path: str, author: str, content: str):
    """Dosyaya yeni not ekler."""
    with get_db() as db:
        db.execute(
            "INSERT INTO dataroom_notes (file_path, author, content) VALUES (?, ?, ?)",
            (file_path, author or "Anonim", content.strip()),
        )
        # Son eklenen notu döner
        row = db.execute(
            "SELECT id, author, content, created_at FROM dataroom_notes WHERE file_path = ? ORDER BY created_at DESC LIMIT 1",
            (file_path,),
        ).fetchone()
        return dict(row) if row else None


def delete_file_note(note_id: int):
    """Bir notu siler."""
    with get_db() as db:
        db.execute("DELETE FROM dataroom_notes WHERE id = ?", (note_id,))


# ---- Görevler (Tasks) ----

TASK_PRIORITIES = ("dusuk", "orta", "yuksek", "acil")
TASK_STATUSES = ("yapilacak", "devam_ediyor", "tamamlandi", "iptal")

_TASK_SELECT = """
    SELECT t.*, e.subject AS related_email_subject,
           COALESCE(e.sender_name, e.sender_email) AS related_email_sender,
           ev.title AS related_event_title, ev.start AS related_event_start
    FROM tasks t
    LEFT JOIN emails e ON e.id = t.related_email_id
    LEFT JOIN events ev ON ev.id = t.related_event_id
"""


def create_task(data: dict) -> int:
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO tasks (title, description, due_date, priority, status,
                                   tags, assignee, related_email_id, related_file_path,
                                   related_event_id)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                (data.get("title") or "").strip(),
                (data.get("description") or "").strip(),
                data.get("due_date") or None,
                data.get("priority") or "orta",
                data.get("status") or "yapilacak",
                (data.get("tags") or "").strip(),
                (data.get("assignee") or "").strip(),
                data.get("related_email_id") or None,
                data.get("related_file_path") or None,
                data.get("related_event_id") or None,
            ),
        )
        return cur.lastrowid


def list_tasks(status: str | None = None, priority: str | None = None,
               tag: str | None = None, q: str = "", due_before: str | None = None) -> list[dict]:
    query = _TASK_SELECT + " WHERE 1=1"
    params = []
    if status:
        query += " AND t.status = ?"
        params.append(status)
    if priority:
        query += " AND t.priority = ?"
        params.append(priority)
    if tag:
        query += " AND (',' || t.tags || ',') LIKE ?"
        params.append(f"%,{tag},%")
    if due_before:
        query += " AND t.due_date IS NOT NULL AND t.due_date != '' AND t.due_date <= ?"
        params.append(due_before)
    if q.strip():
        like = f"%{q.strip()}%"
        query += " AND (t.title LIKE ? OR t.description LIKE ? OR t.tags LIKE ? OR t.assignee LIKE ?)"
        params += [like, like, like, like]
    query += """ ORDER BY
                 CASE WHEN t.status IN ('tamamlandi', 'iptal') THEN 1 ELSE 0 END,
                 CASE WHEN t.due_date IS NULL OR t.due_date = '' THEN 1 ELSE 0 END,
                 t.due_date ASC, t.created_at DESC"""
    with get_db() as db:
        rows = db.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_task(task_id: int) -> dict | None:
    with get_db() as db:
        row = db.execute(_TASK_SELECT + " WHERE t.id = ?", (task_id,)).fetchone()
        return dict(row) if row else None


def update_task(task_id: int, **fields):
    allowed = {"title", "description", "due_date", "priority", "status", "tags",
               "assignee", "related_email_id", "related_file_path", "related_event_id"}
    sets, values = ["updated_at = datetime('now')"], []
    for key, val in fields.items():
        if key in allowed:
            if key in ("title", "description", "tags", "assignee") and isinstance(val, str):
                val = val.strip()
            sets.append(f"{key} = ?")
            values.append(val or None if key in ("due_date", "related_email_id",
                                                   "related_file_path", "related_event_id") else val)
    if len(sets) == 1:
        return
    if fields.get("status") == "tamamlandi":
        sets.append("completed_at = datetime('now')")
    elif "status" in fields:
        sets.append("completed_at = NULL")
    values.append(task_id)
    with get_db() as db:
        db.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", values)


def complete_task(task_id: int, done: bool = True):
    with get_db() as db:
        if done:
            db.execute(
                """UPDATE tasks SET status = 'tamamlandi', completed_at = datetime('now'),
                       updated_at = datetime('now') WHERE id = ?""",
                (task_id,),
            )
        else:
            db.execute(
                """UPDATE tasks SET status = 'yapilacak', completed_at = NULL,
                       updated_at = datetime('now') WHERE id = ?""",
                (task_id,),
            )


def delete_task(task_id: int):
    with get_db() as db:
        db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))


def task_tags() -> list[str]:
    """Var olan tüm etiketlerin benzersiz, sıralı listesi (öneri için)."""
    with get_db() as db:
        rows = db.execute("SELECT tags FROM tasks WHERE tags != ''").fetchall()
    seen = set()
    for r in rows:
        for t in (r["tags"] or "").split(","):
            t = t.strip()
            if t:
                seen.add(t)
    return sorted(seen)


def task_counts() -> dict:
    with get_db() as db:
        rows = db.execute("SELECT status, COUNT(*) AS n FROM tasks GROUP BY status").fetchall()
    return {r["status"]: r["n"] for r in rows}


# ---- Hatırlatmalar (Reminders) ----

REMINDER_STATUSES = ("bekliyor", "tamamlandi", "iptal")

_REMINDER_SELECT = """
    SELECT r.*, e.subject AS related_email_subject,
           COALESCE(e.sender_name, e.sender_email) AS related_email_sender,
           ev.title AS related_event_title, ev.start AS related_event_start,
           t.title AS related_task_title
    FROM reminders r
    LEFT JOIN emails e ON e.id = r.related_email_id
    LEFT JOIN events ev ON ev.id = r.related_event_id
    LEFT JOIN tasks t ON t.id = r.related_task_id
"""


def create_reminder(data: dict) -> int:
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO reminders (text, remind_at, status, related_email_id,
                                       related_file_path, related_event_id, related_task_id)
               VALUES (?,?,?,?,?,?,?)""",
            (
                (data.get("text") or "").strip(),
                data.get("remind_at"),
                data.get("status") or "bekliyor",
                data.get("related_email_id") or None,
                data.get("related_file_path") or None,
                data.get("related_event_id") or None,
                data.get("related_task_id") or None,
            ),
        )
        return cur.lastrowid


def list_reminders(status: str | None = None, upto: str | None = None) -> list[dict]:
    """`upto` verilirse remind_at <= upto olanları da sınırlar (Bugün ekranı için)."""
    query = _REMINDER_SELECT + " WHERE 1=1"
    params = []
    if status:
        query += " AND r.status = ?"
        params.append(status)
    if upto:
        query += " AND r.remind_at <= ?"
        params.append(upto)
    query += " ORDER BY r.remind_at ASC"
    with get_db() as db:
        rows = db.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_reminder(reminder_id: int) -> dict | None:
    with get_db() as db:
        row = db.execute(_REMINDER_SELECT + " WHERE r.id = ?", (reminder_id,)).fetchone()
        return dict(row) if row else None


def update_reminder(reminder_id: int, **fields):
    allowed = {"text", "remind_at", "status", "related_email_id",
               "related_file_path", "related_event_id", "related_task_id"}
    sets, values = ["updated_at = datetime('now')"], []
    for key, val in fields.items():
        if key in allowed:
            if key == "text" and isinstance(val, str):
                val = val.strip()
            if key in ("related_email_id", "related_file_path",
                       "related_event_id", "related_task_id"):
                val = val or None
            sets.append(f"{key} = ?")
            values.append(val)
    if len(sets) == 1:
        return
    values.append(reminder_id)
    with get_db() as db:
        db.execute(f"UPDATE reminders SET {', '.join(sets)} WHERE id = ?", values)


def complete_reminder(reminder_id: int, done: bool = True):
    with get_db() as db:
        db.execute(
            "UPDATE reminders SET status = ?, updated_at = datetime('now') WHERE id = ?",
            ("tamamlandi" if done else "bekliyor", reminder_id),
        )


def delete_reminder(reminder_id: int):
    with get_db() as db:
        db.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))


def due_reminders_unnotified(now_iso: str) -> list[dict]:
    """Zamanı gelmiş ama henüz e-posta bildirimi gönderilmemiş hatırlatmalar (zamanlayıcı için)."""
    with get_db() as db:
        rows = db.execute(
            """SELECT * FROM reminders
               WHERE status = 'bekliyor' AND remind_at <= ? AND notified_at IS NULL""",
            (now_iso,),
        ).fetchall()
        return [dict(r) for r in rows]


def mark_reminder_notified(reminder_id: int):
    with get_db() as db:
        db.execute(
            "UPDATE reminders SET notified_at = datetime('now') WHERE id = ?",
            (reminder_id,),
        )


# ---- Cevap bekliyorum (Awaiting replies) ----

def create_awaiting_reply(data: dict) -> int:
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO awaiting_replies
               (account_id, to_email, to_name, subject, message_id, due_at)
               VALUES (?,?,?,?,?,?)""",
            (
                data.get("account_id"),
                (data.get("to_email") or "").strip(),
                (data.get("to_name") or "").strip(),
                (data.get("subject") or "").strip(),
                data["message_id"],
                data["due_at"],
            ),
        )
        return cur.lastrowid


def list_awaiting_replies(status: str | None = None) -> list[dict]:
    query = "SELECT * FROM awaiting_replies WHERE 1=1"
    params = []
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY due_at ASC"
    with get_db() as db:
        rows = db.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_awaiting_reply(awaiting_id: int) -> dict | None:
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM awaiting_replies WHERE id = ?", (awaiting_id,)
        ).fetchone()
        return dict(row) if row else None


def resolve_awaiting_reply(awaiting_id: int):
    """Kullanıcının elle 'cevaplandı' işaretlemesi."""
    with get_db() as db:
        db.execute(
            """UPDATE awaiting_replies SET status = 'cevaplandi', resolved_at = datetime('now')
               WHERE id = ?""",
            (awaiting_id,),
        )


def cancel_awaiting_reply(awaiting_id: int):
    with get_db() as db:
        db.execute("DELETE FROM awaiting_replies WHERE id = ?", (awaiting_id,))


def resolve_awaiting_replies_by_headers() -> int:
    """Bekleyen kayıtları, eşleşen bir gelen mail varsa otomatik 'cevaplandi' yapar.

    Eşleşme: gelen mailin in_reply_to alanı ya da refs alanı, bizim
    ürettiğimiz message_id'yi içeriyorsa. Header'lar düzgün taşınmazsa
    (bazı istemciler bunu yapmaz) manuel çözümleme yedek olarak kalır.
    Kaç kaydın çözüldüğünü döner.
    """
    with get_db() as db:
        pending = db.execute(
            "SELECT id, message_id FROM awaiting_replies WHERE status = 'bekliyor'"
        ).fetchall()
        resolved = 0
        for p in pending:
            match = db.execute(
                """SELECT id FROM emails
                   WHERE in_reply_to = ? OR (refs IS NOT NULL AND refs LIKE ?)
                   ORDER BY date DESC LIMIT 1""",
                (p["message_id"], f"%{p['message_id']}%"),
            ).fetchone()
            if match:
                db.execute(
                    """UPDATE awaiting_replies
                       SET status = 'cevaplandi', resolved_at = datetime('now'),
                           resolved_email_id = ? WHERE id = ?""",
                    (match["id"], p["id"]),
                )
                resolved += 1
        return resolved


def due_awaiting_replies_unnotified(now_iso: str) -> list[dict]:
    """Süresi geçmiş, henüz bildirilmemiş bekleyen kayıtlar (zamanlayıcı için)."""
    with get_db() as db:
        rows = db.execute(
            """SELECT * FROM awaiting_replies
               WHERE status = 'bekliyor' AND due_at <= ? AND notified_at IS NULL""",
            (now_iso,),
        ).fetchall()
        return [dict(r) for r in rows]


def mark_awaiting_reply_notified(awaiting_id: int):
    with get_db() as db:
        db.execute(
            "UPDATE awaiting_replies SET notified_at = datetime('now') WHERE id = ?",
            (awaiting_id,),
        )


# ---- Kalıcı Donna konuşmaları ----

def create_conversation(title: str = "") -> int:
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO donna_conversations (title) VALUES (?)",
            (title.strip()[:120] or "Yeni sohbet",),
        )
        return cur.lastrowid


def list_conversations() -> list[dict]:
    with get_db() as db:
        rows = db.execute(
            """SELECT c.*,
                      (SELECT content FROM donna_messages m WHERE m.conversation_id = c.id
                       ORDER BY m.id DESC LIMIT 1) AS last_message
               FROM donna_conversations c ORDER BY c.updated_at DESC"""
        ).fetchall()
        return [dict(r) for r in rows]


def get_conversation(conversation_id: int) -> dict | None:
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM donna_conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        return dict(row) if row else None


def rename_conversation(conversation_id: int, title: str):
    with get_db() as db:
        db.execute(
            "UPDATE donna_conversations SET title = ?, updated_at = datetime('now') WHERE id = ?",
            (title.strip()[:120] or "Yeni sohbet", conversation_id),
        )


def delete_conversation(conversation_id: int):
    with get_db() as db:
        db.execute("DELETE FROM donna_messages WHERE conversation_id = ?", (conversation_id,))
        db.execute("DELETE FROM donna_conversations WHERE id = ?", (conversation_id,))


def add_donna_message(conversation_id: int, role: str, content: str,
                      sources: list | None = None) -> int:
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO donna_messages (conversation_id, role, content, sources)
               VALUES (?,?,?,?)""",
            (conversation_id, role, content, json.dumps(sources or [], ensure_ascii=False)),
        )
        db.execute(
            "UPDATE donna_conversations SET updated_at = datetime('now') WHERE id = ?",
            (conversation_id,),
        )
        return cur.lastrowid


def get_conversation_messages(conversation_id: int, limit: int = 20) -> list[dict]:
    """En eski→en yeni sırada son `limit` mesaj."""
    with get_db() as db:
        rows = db.execute(
            """SELECT * FROM donna_messages WHERE conversation_id = ?
               ORDER BY id DESC LIMIT ?""",
            (conversation_id, limit),
        ).fetchall()
    out = []
    for r in reversed(rows):
        d = dict(r)
        try:
            d["sources"] = json.loads(d["sources"]) if d["sources"] else []
        except (TypeError, ValueError):
            d["sources"] = []
        out.append(d)
    return out


# ---- Donna hafızası ----

def create_memory(content: str, source: str = "kullanici_komutu") -> int:
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO donna_memories (content, source) VALUES (?, ?)",
            (content.strip()[:500], source),
        )
        return cur.lastrowid


def list_memories() -> list[dict]:
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM donna_memories ORDER BY created_at DESC, id DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def delete_memory(memory_id: int):
    with get_db() as db:
        db.execute("DELETE FROM donna_memories WHERE id = ?", (memory_id,))
