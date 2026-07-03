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
    created_at TEXT DEFAULT (datetime('now'))
);
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
    """Eski tek hesaplı şemadan çoklu hesaba geçiş."""
    cols = {r["name"] for r in db.execute("PRAGMA table_info(emails)").fetchall()}
    if cols and "account_id" not in cols:
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
                needs_reply, suggested_reply, attachments)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
            ),
        )
        return cur.lastrowid


def list_emails(category: str | None = None, status: str | None = None,
                account_id: int | None = None) -> list[dict]:
    query = """SELECT e.*, a.email AS account_email, a.display_name AS account_name
               FROM emails e LEFT JOIN accounts a ON a.id = e.account_id"""
    conditions, params = [], []
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
    return d
