"""Local SMTP server backed by the shared account registry and mailbox database."""

import re
import socket
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database import store_email
from db import init_db, normalize_email
from users import user_exists

HOST = "127.0.0.1"
PORT = 2525

_MAIL_FROM = re.compile(r"^MAIL FROM:\s*<([^<>]+)>$", re.IGNORECASE)
_RCPT_TO = re.compile(r"^RCPT TO:\s*<([^<>]+)>$", re.IGNORECASE)


def _read_data(reader):
    """Read SMTP DATA, returning the subject and body or None on disconnect."""
    headers = True
    subject = ""
    body_lines = []

    while True:
        line = reader.readline()
        if not line:
            return None
        line = line.rstrip("\r\n")
        if line == ".":
            return subject, "\n".join(body_lines)

        if line.startswith(".."):
            line = line[1:]

        if headers:
            if not line:
                headers = False
            elif line.lower().startswith("subject:"):
                subject = line[len("subject:"):].strip()
        else:
            body_lines.append(line)


def _handle_client(client_socket, client_address):
    print(f"Client connected: {client_address}")
    with client_socket:
        with client_socket.makefile("r", encoding="utf-8") as reader:
            helo_received = False
            smtp_sender = None
            smtp_recipient = None
            client_socket.sendall(b"220 Local SMTP Server Ready\r\n")

            while True:
                line = reader.readline()
                if not line:
                    break

                message = line.rstrip("\r\n")
                command = message.upper()
                print("Client:", message)

                if command.startswith("HELO"):
                    helo_received = True
                    smtp_sender = None
                    smtp_recipient = None
                    client_socket.sendall(b"250 Hello\r\n")

                elif command.startswith("MAIL FROM"):
                    match = _MAIL_FROM.fullmatch(message)
                    try:
                        smtp_sender = normalize_email(match.group(1)) if match else None
                    except ValueError:
                        smtp_sender = None
                    smtp_recipient = None

                    if not helo_received:
                        smtp_sender = None
                        client_socket.sendall(
                            b"503 Bad sequence of commands\r\n"
                        )
                    elif smtp_sender and user_exists(smtp_sender):
                        client_socket.sendall(b"250 Sender accepted\r\n")
                    else:
                        smtp_sender = None
                        client_socket.sendall(b"550 Sender not found\r\n")

                elif command.startswith("RCPT TO"):
                    match = _RCPT_TO.fullmatch(message)
                    try:
                        candidate = normalize_email(match.group(1)) if match else None
                    except ValueError:
                        candidate = None

                    if not smtp_sender:
                        client_socket.sendall(
                            b"503 Bad sequence of commands\r\n"
                        )
                    elif candidate and user_exists(candidate):
                        smtp_recipient = candidate
                        client_socket.sendall(b"250 Recipient accepted\r\n")
                    else:
                        smtp_recipient = None
                        client_socket.sendall(b"550 Recipient not found\r\n")

                elif command == "DATA":
                    if not smtp_sender or not smtp_recipient:
                        client_socket.sendall(
                            b"503 Bad sequence of commands\r\n"
                        )
                        continue

                    client_socket.sendall(
                        b"354 Start mail input; end with <CRLF>.<CRLF>\r\n"
                    )
                    result = _read_data(reader)
                    if result is None:
                        break

                    subject, body = result
                    store_email(smtp_sender, smtp_recipient, subject, body)
                    client_socket.sendall(b"250 Message accepted\r\n")
                    smtp_sender = None
                    smtp_recipient = None

                elif command == "QUIT":
                    client_socket.sendall(b"221 Bye\r\n")
                    break

                else:
                    client_socket.sendall(
                        b"502 Command not implemented\r\n"
                    )

    print(f"Client disconnected: {client_address}")


def serve_forever():
    init_db()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((HOST, PORT))
        server_socket.listen(5)

        print("====================================")
        print("       LOCAL SMTP SERVER")
        print("====================================")
        print("Server started successfully!")
        print("IP Address :", HOST)
        print("Port       :", PORT)
        print("Waiting for clients...")

        while True:
            client_socket, client_address = server_socket.accept()
            try:
                _handle_client(client_socket, client_address)
            except (ConnectionError, OSError) as exc:
                print(f"Client {client_address} disconnected unexpectedly: {exc}")


if __name__ == "__main__":
    try:
        serve_forever()
    except KeyboardInterrupt:
        print("\nSMTP server stopped by user.")
