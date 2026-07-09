"""SQLite veri katmanı."""
import json
import sqlite3
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name TEXT,
    email TEXT UNIQUE,
    password TEXT,
    imap_host TEXT,
    imap_port INTEGER DEFAULT 993,
    smtp_host TEXT,
    smtp_port INTEGER DEFAULT 465,
    smtp_security TEXT DEFAULT 'ssl',   -- ssl | starttls
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
    created_at TEXT DEFAULT (datetime('now'))
);

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
    created_at TEXT DEFAULT (datetime('now'))
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


def init_db():
    with get_db() as db:
        _migrate(db)
        db.executescript(SCHEMA)


# ---- Hesaplar ----

def create_account(data: dict) -> int:
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO accounts
               (display_name, email, password, imap_host, imap_port,
                smtp_host, smtp_port, smtp_security)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                data.get("display_name") or data["email"],
                data["email"],
                data["password"],
                data["imap_host"],
                data.get("imap_port", 993),
                data["smtp_host"],
                data.get("smtp_port", 465),
                data.get("smtp_security", "ssl"),
            ),
        )
        return cur.lastrowid


def list_accounts(include_password: bool = False) -> list[dict]:
    with get_db() as db:
        rows = db.execute("SELECT * FROM accounts ORDER BY id").fetchall()
        accounts = [dict(r) for r in rows]
        if not include_password:
            for a in accounts:
                a.pop("password", None)
        return accounts


def get_account(account_id: int) -> dict | None:
    with get_db() as db:
        row = db.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        return dict(row) if row else None


def get_account_by_email(email_addr: str) -> dict | None:
    with get_db() as db:
        row = db.execute("SELECT * FROM accounts WHERE email = ?", (email_addr,)).fetchone()
        return dict(row) if row else None


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
                data.get("password", ""),
                data.get("color") or CALENDAR_COLORS[n % len(CALENDAR_COLORS)],
            ),
        )
        return cur.lastrowid


def list_calendars(include_password: bool = False) -> list[dict]:
    with get_db() as db:
        rows = db.execute("SELECT * FROM calendars ORDER BY id").fetchall()
        cals = [dict(r) for r in rows]
        if not include_password:
            for c in cals:
                c.pop("password", None)
                c.pop("username", None)
                c.pop("url", None)
        return cals


def get_calendar(calendar_id: int) -> dict | None:
    with get_db() as db:
        row = db.execute("SELECT * FROM calendars WHERE id = ?", (calendar_id,)).fetchone()
        return dict(row) if row else None


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
                      share_downloads FROM dataroom_meta"""
        ).fetchall()
        return {
            r["path"]: {
                "note": r["note"],
                "tags": r["tags"],
                "favorite": bool(r["favorite"]),
                "share_token": r["share_token"],
                "share_expires": r["share_expires"],
                "share_downloads": r["share_downloads"] or 0,
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


def insert_email(data: dict) -> int:
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO emails
               (account_id, message_id, imap_uid, sender_name, sender_email,
                subject, date, body_text, category, priority, summary,
                needs_reply, suggested_reply, attachments, event_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
