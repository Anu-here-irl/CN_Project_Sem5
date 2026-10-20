# POP3 retrieval module

The POP3 server uses the shared account registry in
`instance/mail_system_web.db` for account lookup and password verification. It
uses the existing `smtp_module/mailbox.db` for messages, and serves only the
authenticated account's mailbox. Passwords are stored as Werkzeug hashes.

## Run on Windows

Start the SMTP and POP3 servers and the Flask app in separate terminals. From
the project folder:

```powershell
py pop3_module\pop3_server.py
```

The server listens on `127.0.0.1:1110`. It supports usernames or full
`@localmail.com` addresses followed by the account's Flask password:

```text
USER bob@localmail.com
PASS <the password used to register bob>
STAT
LIST
RETR 1
DELE 1
RSET
QUIT
```

`RETR` marks the email as read. `DELE` marks a message for deletion in the
current session; deletion is committed only by `QUIT`. `RSET` cancels pending
deletion marks. Message numbers are positions in the current mailbox listing,
not SQLite IDs.

The services bind to loopback and POP3 is unencrypted, so this is for local
demonstration only. The Flask bridge uses a local delegated credential; users
of the POP3 client authenticate with their account password.
