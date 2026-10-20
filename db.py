"""SQLite access for Flask web accounts and the UI's email history."""
import os
import re
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(
    os.environ.get(
        "LOCALMAIL_WEB_DB",
        str(BASE_DIR / "instance" / "mail_system_web.db"),
    )
).resolve()
INSTANCE_DIR = DB_PATH.parent
DB_NAME = str(DB_PATH)  # Retained for compatibility with any existing imports.
LOCAL_DOMAIN = "localmail.com"
_USERNAME_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9._-]{0,30}[a-z0-9])?\Z")


def get_db_connection():
    """Open the dedicated Flask database at a stable, explicit path."""
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def normalize_username(value: str) -> str:
    """Return the local part of a supported local email identity."""
    value = (value or "").strip().lower()
    if "@" in value:
        username, domain = value.rsplit("@", 1)
        if domain != LOCAL_DOMAIN:
            raise ValueError(f"Email addresses must use @{LOCAL_DOMAIN}.")
    else:
        username = value

    if not _USERNAME_PATTERN.fullmatch(username):
        raise ValueError(
            "Use 1-32 letters, numbers, dots, underscores, or hyphens; "
            "the first and last characters must be letters or numbers."
        )
    return username


def normalize_email(value: str) -> str:
    """Normalize a username or local email address to its canonical address."""
    return f"{normalize_username(value)}@{LOCAL_DOMAIN}"


def get_account_by_email(email: str):
    """Look up an account in the shared Flask/protocol account registry."""
    try:
        canonical_email = normalize_email(email)
    except ValueError:
        return None

    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT id, username, email, password_hash FROM users WHERE email = ?",
            (canonical_email,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_account_by_id(user_id: int):
    """Look up an account by its stable Flask session identifier."""
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT id, username, email, password_hash FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def init_db():
    """Create missing Flask tables without dropping existing user data."""
    schema_path = BASE_DIR / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")
    conn = get_db_connection()
    try:
        conn.executescript(schema_sql)
        user_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(users)")
        }
        if "email" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        email_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(emails)")
        }
        if "mailbox_id" not in email_columns:
            conn.execute("ALTER TABLE emails ADD COLUMN mailbox_id INTEGER")

        conn.execute(
            """
            UPDATE users
            SET email = CASE
                WHEN instr(username, '@') > 0 THEN lower(username)
                ELSE lower(username || '@localmail.com')
            END
            WHERE email IS NULL OR email = ''
            """
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)"
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_emails_mailbox_id
            ON emails(mailbox_id)
            WHERE folder = 'inbox' AND mailbox_id IS NOT NULL
            """
        )
        conn.commit()
    finally:
        conn.close()
    print(f"Flask database initialized: {DB_NAME}")


if __name__ == "__main__":
    init_db()
