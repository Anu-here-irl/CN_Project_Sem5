import sqlite3

DATABASE_NAME = "mailbox.db"

connection = sqlite3.connect(DATABASE_NAME)
cursor = connection.cursor()

# Add is_read column to the existing emails table
cursor.execute("""
    ALTER TABLE emails
    ADD COLUMN is_read INTEGER DEFAULT 0
""")

connection.commit()
connection.close()

print("is_read column added successfully!")