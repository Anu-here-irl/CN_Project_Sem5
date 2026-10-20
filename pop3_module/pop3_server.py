
"""Local POP3 server for Phase 2.
Uses the existing smtp_module/mailbox.db.
"""

import socket
import sqlite3
import threading
import sys
import hmac
import os
from pathlib import Path
from werkzeug.security import check_password_hash

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db import get_account_by_email, init_db, normalize_email

DATABASE_PATH = Path(
    os.environ.get(
        "LOCALMAIL_MAILBOX_DB",
        str(PROJECT_ROOT / "smtp_module" / "mailbox.db"),
    )
).resolve()

HOST = "127.0.0.1"
PORT = 1110


def mailbox_emails(email):
    """Return emails belonging only to this user's mailbox."""
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            """
            SELECT id, sender, recipient, subject, body, timestamp, is_read
            FROM emails
            WHERE recipient = ?
            ORDER BY id
            """,
            (email,),
        ).fetchall()


def format_message(message):
    """Format a stored email for POP3 RETR."""
    body = (message["body"] or "").replace("\r\n", "\n").replace("\r", "\n")
    body = body.replace("\n", "\r\n")
    return (
        f"From: {message['sender']}\r\n"
        f"To: {message['recipient']}\r\n"
        f"Subject: {message['subject'] or ''}\r\n"
        f"Date: {message['timestamp'] or ''}\r\n"
        f"X-Local-Mailbox-ID: {message['id']}\r\n"
        f"\r\n"
        f"{body}"
    )


def message_size(message):
    return len(format_message(message).encode("utf-8"))


def send_line(stream, line):
    stream.write((line + "\r\n").encode("utf-8"))
    stream.flush()


def send_multiline(stream, text):
    """Send a POP3 multiline response with dot-stuffing."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    for line in normalized.replace("\n", "\r\n").split("\r\n"):
        if line.startswith("."):
            line = "." + line
        send_line(stream, line)
    send_line(stream, ".")


def mark_as_read(message_id, username):
    """Mark only the specified user's email as read."""
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.execute(
            """
            UPDATE emails
            SET is_read = 1
            WHERE id = ? AND recipient = ?
            """,
            (message_id, username),
        )
        conn.commit()

        if cursor.rowcount == 0:
            print(
                f"[POP3] No matching email to mark read: "
                f"id={message_id}, user={username}"
            )
        else:
            print(
                f"[POP3] Marked email id={message_id} "
                f"as read for {username}"
            )


def handle_client(client, address):
    print(f"[POP3] Connected: {address}")

    with client:
        stream = client.makefile("rwb")
        state = "AUTH"
        username = None
        deleted_ids = set()

        try:
            send_line(stream, "+OK Local POP3 server ready")

            while True:
                raw = stream.readline()

                if not raw:
                    break

                command_line = raw.decode(
                    "utf-8", errors="replace"
                ).rstrip("\r\n")

                if not command_line.strip():
                    send_line(stream, "-ERR Empty command")
                    continue

                command, separator, argument = command_line.partition(" ")
                command = command.upper()
                if not separator:
                    argument = ""

                # QUIT closes the session and commits pending deletions.
                if command == "QUIT":
                    if state == "TRANSACTION" and deleted_ids:
                        ids = sorted(deleted_ids)
                        placeholders = ",".join("?" for _ in ids)

                        with sqlite3.connect(DATABASE_PATH) as conn:
                            conn.execute(
                                f"""
                                DELETE FROM emails
                                WHERE recipient = ?
                                AND id IN ({placeholders})
                                """,
                                [username, *ids],
                            )
                            conn.commit()

                        print(
                            f"[POP3] Deleted {len(ids)} email(s) "
                            f"for {username}"
                        )

                    send_line(stream, "+OK POP3 session ended")
                    break

                # Authentication state.
                if state == "AUTH":
                    if command == "USER":
                        try:
                            email_address = normalize_email(argument)
                            account = get_account_by_email(email_address)
                        except ValueError:
                            account = None

                        if account:
                            username = account["email"]
                            send_line(
                                stream,
                                "+OK User accepted; send PASS",
                            )
                        else:
                            username = None
                            send_line(stream, "-ERR Invalid user")

                    elif command == "PASS":
                        if username is None:
                            send_line(stream, "-ERR Send USER first")

                        else:
                            account = get_account_by_email(username)
                            if account is None:
                                username = None
                                send_line(stream, "-ERR Invalid user")
                                continue

                            # The Flask bridge sends the stored hash as a local
                            # delegated credential; external POP3 clients send
                            # the user's password and are verified normally.
                            if argument.startswith("HASH:"):
                                password_ok = hmac.compare_digest(
                                    argument[5:], account["password_hash"]
                                )
                            else:
                                password_ok = check_password_hash(
                                    account["password_hash"], argument
                                )

                            if password_ok:
                                state = "TRANSACTION"
                                deleted_ids.clear()
                                send_line(
                                    stream,
                                    "+OK Mailbox locked and ready",
                                )
                            else:
                                username = None
                                send_line(stream, "-ERR Invalid password")

                    else:
                        send_line(stream, "-ERR Authenticate first")

                    continue

                # Commands in the authenticated transaction state.
                if command in ("USER", "PASS"):
                    send_line(stream, "-ERR Already authenticated")

                elif command == "STAT":
                    messages = [
                        m for m in mailbox_emails(username)
                        if m["id"] not in deleted_ids
                    ]

                    total_size = sum(message_size(m) for m in messages)
                    send_line(
                        stream,
                        f"+OK {len(messages)} {total_size}",
                    )

                elif command == "LIST":
                    messages = [
                        m for m in mailbox_emails(username)
                        if m["id"] not in deleted_ids
                    ]

                    if argument:
                        try:
                            number = int(argument)

                            if not 1 <= number <= len(messages):
                                raise ValueError

                            message = messages[number - 1]
                            send_line(
                                stream,
                                f"+OK {number} {message_size(message)}",
                            )

                        except ValueError:
                            send_line(stream, "-ERR No such message")

                    else:
                        send_line(
                            stream,
                            f"+OK {len(messages)} messages",
                        )

                        for number, message in enumerate(messages, 1):
                            send_line(
                                stream,
                                f"{number} {message_size(message)}",
                            )

                        send_line(stream, ".")

                elif command == "RETR":
                    try:
                        number = int(argument)
                        messages = [
                            m for m in mailbox_emails(username)
                            if m["id"] not in deleted_ids
                        ]

                        if not 1 <= number <= len(messages):
                            raise ValueError

                        message = messages[number - 1]

                        send_line(
                            stream,
                            f"+OK {message_size(message)} octets",
                        )
                        send_multiline(stream, format_message(message))
                        mark_as_read(message["id"], username)

                    except ValueError:
                        send_line(stream, "-ERR No such message")

                elif command == "DELE":
                    try:
                        number = int(argument)
                        messages = [
                            m for m in mailbox_emails(username)
                            if m["id"] not in deleted_ids
                        ]

                        if not 1 <= number <= len(messages):
                            raise ValueError

                        message_id = messages[number - 1]["id"]
                        deleted_ids.add(message_id)

                        send_line(
                            stream,
                            f"+OK Message {number} marked for deletion",
                        )

                    except ValueError:
                        send_line(stream, "-ERR No such message")

                elif command == "RSET":
                    deleted_ids.clear()
                    send_line(stream, "+OK Deletion marks cleared")

                elif command == "NOOP":
                    send_line(stream, "+OK")

                else:
                    send_line(stream, "-ERR Unknown command")

        except (OSError, sqlite3.Error) as exc:
            print(f"[POP3] Client {address} error: {exc}")

        finally:
            stream.close()
            print(f"[POP3] Disconnected: {address}")


def serve_forever():
    init_db()
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Shared database not found: {DATABASE_PATH}"
        )

    # Fail early if the expected database table is missing.
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute("SELECT id FROM emails LIMIT 1")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen()

        print("LOCAL POP3 SERVER")
        print(f"Listening on {HOST}:{PORT}")
        print(f"Shared database: {DATABASE_PATH}")

        while True:
            client, address = server.accept()
            threading.Thread(
                target=handle_client,
                args=(client, address),
                daemon=True,
            ).start()


if __name__ == "__main__":
    serve_forever()
   