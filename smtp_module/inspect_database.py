import sqlite3

DATABASE_NAME = "mailbox.db"

connection = sqlite3.connect(DATABASE_NAME)
cursor = connection.cursor()

print("Current database schema:")
print("------------------------")

cursor.execute("PRAGMA table_info(emails)")

columns = cursor.fetchall()

for column in columns:
    print(column)

connection.close()