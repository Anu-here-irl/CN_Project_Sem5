import sqlite3

DATABASE_NAME = "mailbox.db"

connection = sqlite3.connect(DATABASE_NAME)
cursor = connection.cursor()

# Add timestamp column to the existing emails table
cursor.execute("""
    ALTER TABLE emails
    ADD COLUMN timestamp TEXT
""")

connection.commit()
connection.close()

print("Timestamp column added successfully!")