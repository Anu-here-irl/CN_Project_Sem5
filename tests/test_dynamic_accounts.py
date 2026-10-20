import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMP_ROOT = tempfile.TemporaryDirectory(prefix="localmail-tests-")
TEST_ROOT = Path(TEMP_ROOT.name)
os.environ["LOCALMAIL_WEB_DB"] = str(TEST_ROOT / "mail_system_web.db")
os.environ["LOCALMAIL_MAILBOX_DB"] = str(TEST_ROOT / "mailbox.db")
sys.path.insert(0, str(PROJECT_ROOT))

import app as app_module
import db
import mail_service
import smtp_module.database as smtp_database
from werkzeug.security import check_password_hash


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_port(port, process):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Test server exited early with code {process.returncode}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise TimeoutError(f"Test server did not listen on port {port}")


class DynamicAccountIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db()
        cls.smtp_port = _free_port()
        cls.pop3_port = _free_port()
        while cls.pop3_port == cls.smtp_port:
            cls.pop3_port = _free_port()
        mail_service.SMTP_PORT = cls.smtp_port
        mail_service.POP3_PORT = cls.pop3_port
        test_env = os.environ.copy()

        smtp_script = (
            f"import sys; sys.path.insert(0, {str(PROJECT_ROOT / 'smtp_module')!r}); "
            f"import smtp_server; smtp_server.PORT = {cls.smtp_port}; "
            "smtp_server.serve_forever()"
        )
        pop3_script = (
            f"import sys; sys.path.insert(0, {str(PROJECT_ROOT)!r}); "
            "import pop3_module.pop3_server as server; "
            f"server.PORT = {cls.pop3_port}; server.serve_forever()"
        )
        cls.smtp_process = subprocess.Popen(
            [sys.executable, "-c", smtp_script],
            cwd=PROJECT_ROOT,
            env=test_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _wait_for_port(cls.smtp_port, cls.smtp_process)
        cls.pop3_process = subprocess.Popen(
            [sys.executable, "-c", pop3_script],
            cwd=PROJECT_ROOT,
            env=test_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _wait_for_port(cls.pop3_port, cls.pop3_process)
        app_module.app.config.update(TESTING=True)

    @classmethod
    def tearDownClass(cls):
        for process in (cls.smtp_process, cls.pop3_process):
            process.terminate()
            process.wait(timeout=5)
        TEMP_ROOT.cleanup()

    def setUp(self):
        conn = db.get_db_connection()
        try:
            conn.execute("DELETE FROM emails")
            conn.execute("DELETE FROM users")
            conn.commit()
        finally:
            conn.close()

    def _register(self, username, password):
        client = app_module.app.test_client()
        response = client.post(
            "/register",
            data={"username": username, "password": password},
        )
        self.assertEqual(response.status_code, 302)
        return client

    def _login(self, username, password):
        client = app_module.app.test_client()
        response = client.post(
            "/login",
            data={"username": username, "password": password},
        )
        self.assertEqual(response.status_code, 302)
        return client

    def test_registration_creates_hashed_database_backed_account(self):
        client = self._register("anu", "anu-secret")

        account = db.get_account_by_email("anu@localmail.com")
        self.assertIsNotNone(account)
        self.assertEqual(account["username"], "anu")
        self.assertNotEqual(account["password_hash"], "anu-secret")
        self.assertTrue(check_password_hash(account["password_hash"], "anu-secret"))

        duplicate = client.post(
            "/register",
            data={"username": "anu@localmail.com", "password": "another"},
        )
        self.assertEqual(duplicate.status_code, 200)
        conn = db.get_db_connection()
        try:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1
            )
        finally:
            conn.close()

        wrong_password = app_module.app.test_client().post(
            "/login",
            data={"username": "anu", "password": "wrong"},
        )
        self.assertEqual(wrong_password.status_code, 200)
        self.assertIn(b"Invalid username or password", wrong_password.data)

    def test_registered_users_exchange_mail_and_pop3_isolates_mailboxes(self):
        alice_password = "alice-test-password"
        anu_password = "anu-test-password"
        bob_password = "bob-test-password"
        for username, password in (
            ("alice", alice_password),
            ("anu", anu_password),
            ("bob", bob_password),
            ("charlie", "charlie-test-password"),
        ):
            self._register(username, password)

        alice = self._login("alice", alice_password)
        anu = self._login("anu@localmail.com", anu_password)
        bob = self._login("bob", bob_password)

        send_response = alice.post(
            "/compose",
            data={
                "recipient": "anu",
                "subject": "Dynamic account test",
                "body": "Hello Anu!\n\n.leading dot line\nEnd.",
                "sender": "bob",
            },
        )
        self.assertEqual(
            send_response.status_code,
            302,
            send_response.data.decode("utf-8"),
        )
        conn = db.get_db_connection()
        try:
            sent_rows = conn.execute(
                "SELECT sender, recipient, subject FROM emails WHERE folder = 'sent'"
            ).fetchall()
            self.assertEqual(
                [(row["sender"], row["recipient"], row["subject"]) for row in sent_rows],
                [("alice", "anu@localmail.com", "Dynamic account test")],
            )
        finally:
            conn.close()

        self.assertEqual(anu.post("/fetch-mail").status_code, 302)
        self.assertEqual(anu.post("/fetch-mail").status_code, 302)
        conn = db.get_db_connection()
        try:
            inbox_rows = conn.execute(
                """SELECT sender, recipient, subject, body, mailbox_id
                   FROM emails WHERE folder = 'inbox'"""
            ).fetchall()
            self.assertEqual(len(inbox_rows), 1)
            self.assertEqual(inbox_rows[0]["sender"], "alice@localmail.com")
            self.assertEqual(inbox_rows[0]["recipient"], "anu@localmail.com")
            self.assertEqual(inbox_rows[0]["subject"], "Dynamic account test")
            self.assertIn(".leading dot line", inbox_rows[0]["body"])
            self.assertIsNotNone(inbox_rows[0]["mailbox_id"])
        finally:
            conn.close()

        self.assertEqual(
            anu.post(
                "/compose",
                data={
                    "recipient": "alice",
                    "subject": "Anu replies",
                    "body": "Reply from Anu.",
                },
            ).status_code,
            302,
        )
        self.assertEqual(
            anu.post(
                "/compose",
                data={
                    "recipient": "bob@localmail.com",
                    "subject": "Anu to Bob",
                    "body": "Hello Bob.",
                },
            ).status_code,
            302,
        )
        self.assertEqual(alice.post("/fetch-mail").status_code, 302)
        self.assertEqual(alice.post("/fetch-mail").status_code, 302)
        self.assertEqual(bob.post("/fetch-mail").status_code, 302)
        self.assertEqual(bob.post("/fetch-mail").status_code, 302)

        conn = db.get_db_connection()
        try:
            inbox_counts = {
                recipient: conn.execute(
                    """SELECT COUNT(*) FROM emails
                       WHERE folder = 'inbox' AND recipient = ?""",
                    (recipient,),
                ).fetchone()[0]
                for recipient in (
                    "alice@localmail.com",
                    "anu@localmail.com",
                    "bob@localmail.com",
                )
            }
            self.assertEqual(
                inbox_counts,
                {
                    "alice@localmail.com": 1,
                    "anu@localmail.com": 1,
                    "bob@localmail.com": 1,
                },
            )
            alice_reply = conn.execute(
                """SELECT sender, recipient, subject, body, timestamp, mailbox_id
                   FROM emails
                   WHERE folder = 'inbox' AND recipient = 'alice@localmail.com'"""
            ).fetchone()
            bob_inbox = conn.execute(
                """SELECT sender, recipient, subject, body, timestamp, mailbox_id
                   FROM emails
                   WHERE folder = 'inbox' AND recipient = 'bob@localmail.com'"""
            ).fetchone()
            self.assertEqual(alice_reply["sender"], "anu@localmail.com")
            self.assertEqual(alice_reply["subject"], "Anu replies")
            self.assertEqual(alice_reply["body"], "Reply from Anu.")
            self.assertTrue(alice_reply["timestamp"])
            self.assertIsNotNone(alice_reply["mailbox_id"])
            self.assertEqual(bob_inbox["sender"], "anu@localmail.com")
            self.assertEqual(bob_inbox["subject"], "Anu to Bob")
            self.assertEqual(bob_inbox["body"], "Hello Bob.")
            self.assertTrue(bob_inbox["timestamp"])
            self.assertIsNotNone(bob_inbox["mailbox_id"])

            sent_counts = {
                sender: conn.execute(
                    "SELECT COUNT(*) FROM emails WHERE folder = 'sent' AND sender = ?",
                    (sender,),
                ).fetchone()[0]
                for sender in ("alice", "anu", "bob")
            }
            self.assertEqual(sent_counts, {"alice": 1, "anu": 2, "bob": 0})
        finally:
            conn.close()

        self.assertIn(b"Dynamic account test", alice.get("/sent").data)
        self.assertNotIn(b"Dynamic account test", bob.get("/sent").data)
        self.assertIn(b"Anu replies", alice.get("/inbox").data)
        self.assertIn(b"Anu to Bob", bob.get("/inbox").data)
        self.assertNotIn(b"Anu to Bob", anu.get("/inbox").data)

        response = self._pop3_exchange(
            "USER anu@localmail.com",
            f"PASS {anu_password}",
            "STAT",
            "QUIT",
        )
        self.assertTrue(response[2].startswith("+OK Mailbox locked"))
        self.assertEqual(response[3].split()[1], "1")

        bob_mailbox = self._pop3_exchange(
            "USER bob",
            f"PASS {bob_password}",
            "STAT",
            "QUIT",
        )
        self.assertEqual(bob_mailbox[3].split()[1], "1")

        failed_login = self._pop3_exchange(
            "USER anu",
            "PASS incorrect",
            "QUIT",
        )
        self.assertTrue(failed_login[2].startswith("-ERR Invalid password"))

    def test_smtp_rejects_unknown_recipients(self):
        self._register("alice", "alice-password")
        with socket.create_connection(("127.0.0.1", self.smtp_port)) as sock:
            reader = sock.makefile("rb")
            self.assertTrue(reader.readline().startswith(b"220"))
            sock.sendall(b"HELO localhost\r\n")
            self.assertTrue(reader.readline().startswith(b"250"))
            sock.sendall(b"MAIL FROM:<alice@localmail.com>\r\n")
            self.assertTrue(reader.readline().startswith(b"250"))
            sock.sendall(b"RCPT TO:<missing@localmail.com>\r\n")
            self.assertTrue(reader.readline().startswith(b"550"))
            sock.sendall(b"QUIT\r\n")
            reader.readline()

    def test_stopped_mail_services_report_errors_in_flask(self):
        self._register("alice", "alice-password")
        client = self._login("alice", "alice-password")
        smtp_port = mail_service.SMTP_PORT
        pop3_port = mail_service.POP3_PORT
        try:
            mail_service.SMTP_PORT = _free_port()
            send_response = client.post(
                "/compose",
                data={
                    "recipient": "alice",
                    "subject": "Unavailable server",
                    "body": "This should not be sent.",
                },
            )
            self.assertEqual(send_response.status_code, 200)
            self.assertIn(b"Failed to send email", send_response.data)

            mail_service.POP3_PORT = _free_port()
            fetch_response = client.post("/fetch-mail", follow_redirects=True)
            self.assertEqual(fetch_response.status_code, 200)
            self.assertIn(b"Could not retrieve mail via POP3", fetch_response.data)
        finally:
            mail_service.SMTP_PORT = smtp_port
            mail_service.POP3_PORT = pop3_port

    def _pop3_exchange(self, *commands):
        responses = []
        with socket.create_connection(("127.0.0.1", self.pop3_port)) as sock:
            reader = sock.makefile("rb")
            responses.append(reader.readline().decode().strip())
            for command in commands:
                sock.sendall((command + "\r\n").encode())
                responses.append(reader.readline().decode().strip())
        return responses


if __name__ == "__main__":
    unittest.main()
