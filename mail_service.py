"""Bridge the Flask UI to the project's local SMTP and POP3 servers.

The SMTP/POP3 mailbox lives in smtp_module/mailbox.db. Flask's own database
stores web accounts and a UI-friendly sent/inbox view.
"""

from __future__ import annotations

import socket
from email.parser import Parser

from db import get_account_by_email, get_db_connection, normalize_email

SMTP_HOST = "127.0.0.1"
SMTP_PORT = 2525
POP3_HOST = "127.0.0.1"
POP3_PORT = 1110
SOCKET_TIMEOUT = 5


def _read_smtp_response(reader) -> str:
    line = reader.readline()
    if not line:
        raise ConnectionError("SMTP server closed the connection unexpectedly.")
    return line.decode("utf-8", errors="replace").rstrip("\r\n")


def _smtp_command(sock, reader, command: str, expected_codes: tuple[str, ...]) -> str:
    sock.sendall((command + "\r\n").encode("utf-8"))
    response = _read_smtp_response(reader)
    if not response.startswith(expected_codes):
        raise RuntimeError(f"SMTP command {command.split(' ', 1)[0]} failed: {response}")
    return response


def send_email(sender: str, recipient: str, subject: str, body: str):
    """Send through the real local SMTP server; log to Flask DB only on success."""
    try:
        sender_address = normalize_email(sender)
        recipient_address = normalize_email(recipient)
    except ValueError as exc:
        return False, str(exc)

    sender_account = get_account_by_email(sender_address)
    if sender_account is None:
        return False, f"'{sender}' is not a registered local sender."
    if get_account_by_email(recipient_address) is None:
        return False, f"'{recipient}' is not a registered local recipient."
    if not body.strip():
        return False, "Message body cannot be empty."

    safe_subject = (subject or "").replace("\r", " ").replace("\n", " ")
    safe_body = body.replace("\r\n", "\n").replace("\r", "\n")
    # SMTP DATA uses a single dot on a line to end the message; dot-stuff lines.
    body_lines = [("." + line if line.startswith(".") else line) for line in safe_body.split("\n")]
    data = (
        f"From: {sender_address}\r\n"
        f"To: {recipient_address}\r\n"
        f"Subject: {safe_subject}\r\n"
        f"\r\n"
        + "\r\n".join(body_lines)
        + "\r\n.\r\n"
    )

    try:
        with socket.create_connection((SMTP_HOST, SMTP_PORT), timeout=SOCKET_TIMEOUT) as sock:
            sock.settimeout(SOCKET_TIMEOUT)
            with sock.makefile("rb") as reader:
                greeting = _read_smtp_response(reader)
                if not greeting.startswith("220"):
                    raise RuntimeError(f"SMTP server rejected connection: {greeting}")
                _smtp_command(sock, reader, "HELO localhost", ("250",))
                _smtp_command(sock, reader, f"MAIL FROM:<{sender_address}>", ("250",))
                _smtp_command(sock, reader, f"RCPT TO:<{recipient_address}>", ("250",))
                _smtp_command(sock, reader, "DATA", ("354",))
                sock.sendall(data.encode("utf-8"))
                final_response = _read_smtp_response(reader)
                if not final_response.startswith("250"):
                    raise RuntimeError(f"SMTP server did not accept the message: {final_response}")
                try:
                    _smtp_command(sock, reader, "QUIT", ("221",))
                except (OSError, RuntimeError, ConnectionError):
                    # Message has already been accepted; QUIT failure does not undo it.
                    pass

        # Preserve the existing Sent UI. Log only after the SMTP server accepts DATA.
        conn = get_db_connection()
        try:
            conn.execute(
                """INSERT INTO emails
                   (sender, recipient, subject, body, folder, category, is_read)
                   VALUES (?, ?, ?, ?, 'sent', 'Unclassified', 1)""",
                (
                    sender_account["username"],
                    recipient_address,
                    safe_subject,
                    safe_body,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return True, "SMTP server accepted the email."
    except (OSError, RuntimeError, ConnectionError, TimeoutError) as exc:
        return False, str(exc)
    except Exception as exc:
        return False, f"Email was accepted by SMTP, but the Sent history could not be updated: {exc}"


def _pop3_read_line(reader) -> str:
    line = reader.readline()
    if not line:
        raise ConnectionError("POP3 server closed the connection unexpectedly.")
    return line.decode("utf-8", errors="replace").rstrip("\r\n")


def _pop3_command(sock, reader, command: str) -> str:
    sock.sendall((command + "\r\n").encode("utf-8"))
    response = _pop3_read_line(reader)
    if not response.startswith("+OK"):
        raise RuntimeError(f"POP3 command {command.split(' ', 1)[0]} failed: {response}")
    return response


def _pop3_multiline(reader) -> str:
    lines = []
    while True:
        line = _pop3_read_line(reader)
        if line == ".":
            break
        if line.startswith(".."):
            line = line[1:]
        lines.append(line)
    return "\n".join(lines)


def fetch_emails(user: str):
    """Retrieve all messages from the real POP3 server for a protocol account."""
    email_address = normalize_email(user)
    account = get_account_by_email(email_address)
    if account is None:
        raise ValueError(f"'{user}' is not a registered local account.")

    retrieved = []
    with socket.create_connection((POP3_HOST, POP3_PORT), timeout=SOCKET_TIMEOUT) as sock:
        sock.settimeout(SOCKET_TIMEOUT)
        with sock.makefile("rb") as reader:
            greeting = _pop3_read_line(reader)
            if not greeting.startswith("+OK"):
                raise RuntimeError(f"POP3 server rejected connection: {greeting}")

            _pop3_command(sock, reader, f"USER {email_address}")
            _pop3_command(sock, reader, f"PASS HASH:{account['password_hash']}")
            stat_response = _pop3_command(sock, reader, "STAT")
            parts = stat_response.split()
            message_count = int(parts[1]) if len(parts) >= 2 else 0

            for number in range(1, message_count + 1):
                _pop3_command(sock, reader, f"RETR {number}")
                raw_message = _pop3_multiline(reader)
                parsed = Parser().parsestr(raw_message)
                sender = (parsed.get("From") or "").strip()
                recipient = (parsed.get("To") or email_address).strip()
                subject = (parsed.get("Subject") or "").strip()
                body = parsed.get_payload()
                if not isinstance(body, str):
                    body = ""
                date = (parsed.get("Date") or "").strip()
                mailbox_id = parsed.get("X-Local-Mailbox-ID")
                try:
                    mailbox_id = int(mailbox_id) if mailbox_id else None
                except ValueError:
                    mailbox_id = None
                retrieved.append({
                    "mailbox_id": mailbox_id,
                    "sender": sender,
                    "recipient": recipient,
                    "subject": subject,
                    "body": body,
                    "timestamp": date,
                })

            # QUIT commits any POP3 deletions; this client does not issue DELE.
            _pop3_command(sock, reader, "QUIT")

    return retrieved


def sync_inbox(user: str) -> int:
    """Retrieve POP3 messages and add previously unseen messages to Flask's inbox."""
    email_address = normalize_email(user)
    account = get_account_by_email(email_address)
    if account is None:
        raise ValueError(f"'{user}' is not a registered local account.")

    incoming = fetch_emails(email_address)
    conn = get_db_connection()
    added = 0
    try:
        for mail in incoming:
            mailbox_id = mail["mailbox_id"]
            if mailbox_id is not None:
                existing = conn.execute(
                    """SELECT id FROM emails
                       WHERE folder = 'inbox' AND mailbox_id = ? LIMIT 1""",
                    (mailbox_id,),
                ).fetchone()
            else:
                existing = None
            if existing:
                continue

            legacy_match = conn.execute(
                """SELECT id FROM emails
                   WHERE recipient IN (?, ?) AND sender = ? AND subject = ?
                     AND body = ? AND folder = 'inbox' AND mailbox_id IS NULL
                   LIMIT 1""",
                (
                    account["email"],
                    account["username"],
                    mail["sender"],
                    mail["subject"],
                    mail["body"],
                ),
            ).fetchone()
            if legacy_match:
                if mailbox_id is not None:
                    conn.execute(
                        """UPDATE emails SET mailbox_id = ?
                           WHERE id = ? AND mailbox_id IS NULL""",
                        (mailbox_id, legacy_match["id"]),
                    )
                continue

            inserted = conn.execute(
                """INSERT INTO emails
                   (sender, recipient, subject, body, timestamp, folder,
                    category, is_read, mailbox_id)
                   VALUES (?, ?, ?, ?, ?, 'inbox', 'Unclassified', 0, ?)
                   ON CONFLICT(mailbox_id)
                   WHERE folder = 'inbox' AND mailbox_id IS NOT NULL
                   DO NOTHING""",
                (
                    mail["sender"],
                    account["email"],
                    mail["subject"],
                    mail["body"],
                    mail["timestamp"] or None,
                    mailbox_id,
                ),
            ).rowcount
            added += inserted
        conn.commit()
    finally:
        conn.close()
    return added
