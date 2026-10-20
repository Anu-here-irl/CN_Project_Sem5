# test_database.py
# Test storing an email in the database

import sqlite3


DATABASE_NAME = "mailbox.db"


# Connect to database
connection = sqlite3.connect(DATABASE_NAME)

cursor = connection.cursor()


# Test email
sender = "alice@localmail.com"
recipient = "bob@localmail.com"
subject = "Database Test"
body = "This email is being stored in the mailbox database."


# Insert email into database
cursor.execute("""
    INSERT INTO emails (sender, recipient, subject, body)
    VALUES (?, ?, ?, ?)
""", (sender, recipient, subject, body))


# Save changes
connection.commit()


print("Email stored successfully!")

# Close connection
connection.close()