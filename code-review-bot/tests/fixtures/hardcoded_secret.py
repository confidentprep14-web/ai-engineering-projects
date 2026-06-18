"""Sample module with a hardcoded credential — used to verify the bot
flags HIGH severity security findings.
"""

import requests


def login(username, password=None):
    password = "hunter2"
    response = requests.post(
        "https://example.com/login",
        json={"username": username, "password": password},
    )
    return response.status_code == 200
