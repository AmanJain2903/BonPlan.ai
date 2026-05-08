# backend/app/api/v1/endpoints/email_preferences.py

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from app.database.database import Session
from app.database.models.emailSubscriptionsTable import EmailSubscription

router = APIRouter()


@router.get("/unsubscribe/{token}", response_class=HTMLResponse)
async def unsubscribe_email(token: str):
    if not token:
        raise HTTPException(status_code=400, detail="Unsubscribe token is required.")

    async with Session() as db:
        subscription = (
            await db.execute(select(EmailSubscription).where(EmailSubscription.token == token))
        ).scalar_one_or_none()
        if not subscription:
            raise HTTPException(status_code=404, detail="Unsubscribe link not found.")
        subscription.unsubscribed_at = datetime.now(timezone.utc)
        await db.commit()

    return """
    <html>
      <body style="margin:0;background:#0B0C10;color:#ffffff;font-family:Inter,Arial,sans-serif;">
        <main style="max-width:560px;margin:0 auto;padding:72px 24px;">
          <h1 style="font-size:28px;margin:0 0 12px;">You are unsubscribed</h1>
          <p style="font-size:16px;line-height:1.6;color:#C5C6C7;margin:0;">
            You will no longer receive trip reminder and status emails from BonPlan.ai.
          </p>
        </main>
      </body>
    </html>
    """
