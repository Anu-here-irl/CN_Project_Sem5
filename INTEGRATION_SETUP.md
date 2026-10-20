# Local SMTP/POP3 integration

The Flask application, SMTP server, and POP3 server share one account registry.
Registering a username in the web UI creates `username@localmail.com` in that
registry. The address and Werkzeug password hash are stored in
`instance/mail_system_web.db`; the password is never stored in plaintext.
Existing Alice, Bob, and Charlie accounts and both existing databases are
retained. POP3 `USER`/`PASS` uses the registered account and password.

The message store remains `smtp_module/mailbox.db`. SMTP writes each accepted
message there once, and POP3 exposes only messages addressed to the
authenticated user's local address. The Flask `emails` table is the UI's
sent/inbox history. POP3 message IDs are recorded when imported, so repeated
checks do not duplicate inbox rows; older imported rows are matched and linked
during the first check after the migration.

SMTP has no SMTP AUTH command. It validates envelope sender and recipient
addresses against the registered account table, but an external local SMTP
client can still claim another registered sender address. The Flask compose
route always supplies the signed-in account as sender. Services bind to
`127.0.0.1` and are for local demonstration only.
Flask generates a random session-signing key at startup unless
`LOCALMAIL_SECRET_KEY` is configured; without that environment variable, a
Flask restart requires users to log in again.

## First-time setup on Windows

Run commands from the project folder. Initialization is safe to repeat and
does not drop existing tables or messages:

```powershell
py db.py
```

Flask and both protocol servers also run this initialization automatically.
Database paths are derived from the project files, so starting a server from a
different working directory will not create another mailbox.

## Start the three services

Open three separate terminals.

**Terminal 1 — SMTP server**

```powershell
cd "C:\path\to\CN_PROJECT_2026\smtp_module"
py smtp_server.py
```

Listens on `127.0.0.1:2525`.

**Terminal 2 — POP3 server**

```powershell
cd "C:\path\to\CN_PROJECT_2026"
py pop3_module\pop3_server.py
```

Listens on `127.0.0.1:1110`.

**Terminal 3 — Flask application**

```powershell
cd "C:\path\to\CN_PROJECT_2026"
py app.py
```

The web application is at <http://127.0.0.1:5050>.
Replace `C:\path\to\CN_PROJECT_2026` with the project's actual path.

## Register and test a new account

1. Open the Flask URL and choose **Create one**.
2. Register a username such as `anu` and a password. The address
   `anu@localmail.com` is created automatically. A full address such as
   `anu@localmail.com` may also be used as the registration/login name.
3. Log in as `anu` (or the full address).
4. Compose a message to `alice`, `bob`, `charlie`, or any other registered
   local username/address.
5. Sign in as the recipient and use **Check Mail (POP3)** to import the
   message. Rechecking should not add another copy.

Only local addresses in the `localmail.com` domain are supported. Usernames
may contain letters, numbers, dots, underscores, and hyphens, and must begin
and end with a letter or number. Passwords are shared between Flask login and
POP3 authentication. Since POP3 is unencrypted, keep these services bound to
loopback and do not reuse real-world passwords.
