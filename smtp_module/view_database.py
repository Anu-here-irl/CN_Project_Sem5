import sqlite3

DATABASE_NAME = "mailbox.db"

connection = sqlite3.connect(DATABASE_NAME)
cursor = connection.cursor()

cursor.execute("""
    SELECT id, sender, recipient, subject, body, timestamp, is_read
    FROM emails
""")

emails = cursor.fetchall()

print("==============================================")
print("             EMAIL DATABASE")
print("==============================================")

for email in emails:
    print()
    print("ID        :", email[0])
    print("Sender    :", email[1])
    print("Recipient :", email[2])
    print("Subject   :", email[3])
    print("Body      :", email[4])
    print("Timestamp :", email[5])

    if email[6] == 0:
        print("Status    : Unread")
    else:
        print("Status    : Read")

    print("----------------------------------------------")

connection.close()