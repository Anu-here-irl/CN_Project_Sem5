
import sqlite3
from pathlib import Path

# Always use the mailbox.db in this file's folder
DATABASE_NAME = Path(__file__).resolve().parent / "mailbox.db"

connection = sqlite3.connect(DATABASE_NAME)
cursor = connection.cursor()

try:
    cursor.execute("""
        SELECT id, sender, recipient, subject, body, timestamp, is_read
        FROM emails
        ORDER BY id
    """)

    emails = cursor.fetchall()

    print("==============================================")
    print("             EMAIL DATABASE")
    print("==============================================")
    print("Database:", DATABASE_NAME)
    print("Total emails:", len(emails))

    for email in emails:
        print()
        print("ID        :", email[0])
        print("Sender    :", email[1])
        print("Recipient :", email[2])
        print("Subject   :", email[3])
        print("Body      :", email[4])
        print("Timestamp :", email[5])

        if email[6] == 0:
            print("Status    : Unread (0)")
        else:
            print("Status    : Read (1)")

        print("----------------------------------------------")

except sqlite3.OperationalError as error:
    print("Database error:", error)
    print("The emails table may not exist in this database.")

finally:
    connection.close()
