# backend/app/utils/emailVerification.py

"""
This file contains the functions for email verification.
"""

from app.core.config import settings
from email.mime.text import MIMEText
import smtplib
import jwt
import os

SMTP_LOGIN_EMAIL = settings.SENDER_EMAIL
EMAIL_PASSWORD = settings.GMAIL_APP_PASSWORD

DISPLAY_FROM = "BonPlan.ai <no-reply@bonplan.ai>"

def send_email(to_email, subject, body):
    msg = MIMEText(body, "html")
    msg["Subject"] = subject
    msg["From"] = DISPLAY_FROM
    msg["To"] = to_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_LOGIN_EMAIL, EMAIL_PASSWORD)
            server.sendmail(SMTP_LOGIN_EMAIL, to_email, msg.as_string())
        print("✅ Email sent successfully")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        raise e