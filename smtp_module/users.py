# users.py
# Users for our local email system


VALID_USERS = [
    "alice@localmail.com",
    "bob@localmail.com",
    "charlie@localmail.com"
]


def user_exists(email):

    return email in VALID_USERS