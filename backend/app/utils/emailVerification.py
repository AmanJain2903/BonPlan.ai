# backend/app/utils/emailVerification.py

"""
This file contains the functions for email verification.
"""

import asyncio
import smtplib
from email.mime.text import MIMEText

from app.core.config import settings
from app.logging import get_utils_logger

logger = get_utils_logger("emailVerification")

SMTP_LOGIN_EMAIL = settings.SENDER_EMAIL
EMAIL_PASSWORD = settings.GMAIL_APP_PASSWORD

DISPLAY_FROM = "BonPlan.ai <no-reply@bonplan.ai>"


async def send_email(to_email, subject, body):
    msg = MIMEText(body, "html")
    msg["Subject"] = subject
    msg["From"] = DISPLAY_FROM
    msg["To"] = to_email

    def _blocking_send():
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_LOGIN_EMAIL, EMAIL_PASSWORD)
            server.sendmail(SMTP_LOGIN_EMAIL, to_email, msg.as_string())

    try:
        await asyncio.to_thread(_blocking_send)
        logger.info("Email sent successfully", to=to_email, subject=subject)
    except Exception as e:
        logger.exception("Failed to send email", to=to_email, error=str(e))
        raise
