import sqlite3
from datetime import datetime

DATABASE_NAME = "mailbox.db"


def create_database():
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            recipient TEXT NOT NULL,
            subject TEXT,
            body TEXT,
            timestamp TEXT,
            is_read INTEGER DEFAULT 0
        )
    """)

    connection.commit()
    connection.close()


def store_email(sender, recipient, subject, body):
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()

    # Get the current date and time
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # New emails are unread by default
    is_read = 0

    cursor.execute("""
        INSERT INTO emails
        (sender, recipient, subject, body, timestamp, is_read)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (sender, recipient, subject, body, timestamp, is_read))

    connection.commit()
    connection.close()

    print("Email stored in database successfully!")


create_database()