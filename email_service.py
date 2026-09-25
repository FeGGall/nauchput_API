import os
import smtplib
import random
from email.message import EmailMessage

from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM")


def generate_code():
    return f"{random.randint(0, 999999):06d}"


def send_verification_email(email: str, code: str):
    message = EmailMessage()

    message["Subject"] = "Код подтверждения НаучПуть"
    message["From"] = SMTP_FROM
    message["To"] = email

    message.set_content(
        f"""
Здравствуйте!

Ваш код подтверждения:

{code}

Код действует 10 минут.

НаучПуть
"""
    )

    with smtplib.SMTP_SSL(
        SMTP_HOST,
        SMTP_PORT
    ) as smtp:
        smtp.login(
            SMTP_USER,
            SMTP_PASSWORD
        )

        smtp.send_message(message)