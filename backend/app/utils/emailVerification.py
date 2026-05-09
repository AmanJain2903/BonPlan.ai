# backend/app/utils/emailVerification.py

"""
This file contains the functions for email verification.
"""

import asyncio
import base64
import mimetypes
from pathlib import Path
from typing import Any

import resend

from app.core.config import settings
from app.logging import get_utils_logger

logger = get_utils_logger("emailVerification")

AUTH_EMAIL_ADDRESS = "noreply-auth@bonplanai.com"
SUPPORT_EMAIL_ADDRESS = "support@bonplanai.com"
TRIP_EMAIL_ADDRESS = "noreply-trips@bonplanai.com"
SYSTEM_EMAIL_ADDRESS = "noreply-system@bonplanai.com"
AUTH_EMAIL_FROM = f"BonPlan.ai Auth <{AUTH_EMAIL_ADDRESS}>"
SUPPORT_EMAIL_FROM = f"BonPlan.ai Support <{SUPPORT_EMAIL_ADDRESS}>"
TRIP_EMAIL_FROM = f"BonPlan.ai Trips <{TRIP_EMAIL_ADDRESS}>"
SYSTEM_EMAIL_FROM = f"BonPlan.ai System <{SYSTEM_EMAIL_ADDRESS}>"
BONPLAN_LOGO_CID = "bonplan-logo"
BONPLAN_LOGO_PATH = Path(__file__).resolve().parents[3] / "frontend" / "public" / "logo.png"


def _inline_image_attachments(inline_images: dict[str, str | Path] | None) -> list[dict[str, Any]]:
    attachments: list[dict[str, Any]] = []
    for content_id, image_path in (inline_images or {}).items():
        path = Path(image_path)
        if not path.exists():
            logger.warning("Inline email image missing", content_id=content_id, path=str(path))
            continue
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        attachments.append(
            {
                "content": base64.b64encode(path.read_bytes()).decode("ascii"),
                "filename": path.name,
                "content_type": content_type,
                "inline_content_id": content_id,
            }
        )
    return attachments


def render_email_layout(
    *,
    title: str,
    preheader: str,
    body_html: str,
    eyebrow: str = "BonPlan.ai",
    cta_label: str | None = None,
    cta_url: str | None = None,
    footer_html: str = "",
) -> str:
    logo_src = f"cid:{BONPLAN_LOGO_CID}"
    cta_html = ""
    if cta_label and cta_url:
        cta_html = f"""
        <a href="{cta_url}" style="display:inline-block;background:#66FCF1;color:#0B0C10;text-decoration:none;font-weight:800;border-radius:12px;padding:13px 18px;margin:8px 0 18px;">
          {cta_label}
        </a>
        """
    return f"""
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{preheader}</div>
    <div style="margin:0;padding:0;background:#0B0C10;color:#C5C6C7;font-family:Inter,Arial,sans-serif;">
      <div style="max-width:640px;margin:0 auto;padding:32px 20px;">
        <div style="border:1px solid rgba(255,255,255,0.1);border-radius:18px;background:#1F2833;padding:28px;">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:22px;">
            <img src="{logo_src}" alt="BonPlan.ai" width="36" height="36" style="display:block;border-radius:10px;" />
            <div style="font-size:22px;font-weight:800;color:#ffffff;">BonPlan<span style="color:#66FCF1;">.</span>ai</div>
          </div>
          <div style="font-size:12px;letter-spacing:0.12em;text-transform:uppercase;color:#66FCF1;font-weight:800;margin-bottom:8px;">{eyebrow}</div>
          <h1 style="font-size:26px;line-height:1.2;margin:0 0 16px;color:#ffffff;">{title}</h1>
          <div style="font-size:16px;line-height:1.65;color:#D6D8DA;">
            {body_html}
          </div>
          {cta_html}
          <div style="border-top:1px solid rgba(255,255,255,0.1);margin-top:18px;padding-top:16px;font-size:12px;line-height:1.5;color:rgba(197,198,199,0.68);">
            {footer_html or "BonPlan.ai keeps your trips organized, collaborative, and ready when you are."}
          </div>
        </div>
      </div>
    </div>
    """


def bonplan_inline_images() -> dict[str, Path]:
    return {BONPLAN_LOGO_CID: BONPLAN_LOGO_PATH}


async def send_email(
    to_email: str | list[str],
    subject: str,
    body: str,
    inline_images: dict[str, str | Path] | None = None,
    from_email: str = AUTH_EMAIL_FROM,
):
    params: resend.Emails.SendParams = {
        "from": from_email,
        "to": to_email,
        "subject": subject,
        "html": body,
    }
    attachments = _inline_image_attachments(inline_images)
    if attachments:
        params["attachments"] = attachments

    def _blocking_send():
        if not settings.RESEND_API_KEY:
            raise RuntimeError("RESEND_API_KEY is not configured.")
        resend.api_key = settings.RESEND_API_KEY
        return resend.Emails.send(params)

    try:
        response = await asyncio.to_thread(_blocking_send)
        logger.info("Email sent successfully", to=to_email, subject=subject, from_email=from_email)
        return response
    except Exception as e:
        logger.exception("Failed to send email", to=to_email, subject=subject, from_email=from_email, error=str(e))
        raise
