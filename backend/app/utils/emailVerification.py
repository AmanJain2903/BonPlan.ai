# backend/app/utils/emailVerification.py

"""
This file contains the functions for email verification.
"""

import asyncio
import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from app.core.config import settings
from app.logging import get_utils_logger

logger = get_utils_logger("emailVerification")

SMTP_LOGIN_EMAIL = settings.SENDER_EMAIL
EMAIL_PASSWORD = settings.GMAIL_APP_PASSWORD

DISPLAY_FROM = "BonPlan.ai <no-reply@bonplan.ai>"
BONPLAN_LOGO_CID = "bonplan-logo"
BONPLAN_LOGO_PATH = Path(__file__).resolve().parents[3] / "frontend" / "public" / "logo.png"


async def send_email(to_email, subject, body, inline_images: dict[str, str | Path] | None = None):
    if inline_images:
        msg = MIMEMultipart("related")
        alternative = MIMEMultipart("alternative")
        alternative.attach(MIMEText(body, "html"))
        msg.attach(alternative)

        for content_id, image_path in inline_images.items():
            path = Path(image_path)
            if not path.exists():
                logger.warning("Inline email image missing", content_id=content_id, path=str(path))
                continue
            subtype = path.suffix.lstrip(".").lower() or "png"
            if subtype == "jpg":
                subtype = "jpeg"
            with path.open("rb") as image_file:
                image = MIMEImage(image_file.read(), _subtype=subtype)
            image.add_header("Content-ID", f"<{content_id}>")
            image.add_header("Content-Disposition", "inline", filename=path.name)
            msg.attach(image)
    else:
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
