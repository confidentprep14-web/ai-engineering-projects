"""Sample module with an N+1 query pattern — used to verify the bot
flags performance findings.
"""


def get_user_emails(db, users):
    emails = []
    for user in users:
        record = db.query(f"SELECT email FROM users WHERE id = {user.id}")
        emails.append(record.email)
    return emails
