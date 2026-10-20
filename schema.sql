-- Flask web accounts and UI-friendly email history.
-- Deliberately does not DROP tables: initialization must not erase user data.
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender TEXT NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT,
    body TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    folder TEXT NOT NULL CHECK(folder IN ('inbox', 'sent')),
    category TEXT DEFAULT 'Unclassified',
    is_read INTEGER DEFAULT 0 CHECK(is_read IN (0, 1)),
    mailbox_id INTEGER
);
