# backend/app/api/v1/endpoints/support.py

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import jwt
from sqlalchemy import select

from app.core.config import settings
from app.database.database import Session
from app.database.models.faqTable import FAQ
from app.database.models.supportTicketsTable import SupportTicket, TicketStatus
from app.database.models.usersTable import User
from app.logging import get_api_logger
from app.utils.emailVerification import send_email

logger = get_api_logger("api.support")
router = APIRouter()


async def _decode_token(token: str) -> str:
    if not token:
        raise HTTPException(status_code=400, detail="Token is required.")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session. Please log in again.")
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid token.")
    return user_id


async def _verify_admin(token: str) -> str:
    user_id = await _decode_token(token)
    async with Session() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        if not user.is_admin:
            raise HTTPException(status_code=403, detail="Admin privileges required.")
    return user_id


# ── Pydantic models ───────────────────────────────────────────────────────────

class SubmitTicketBody(BaseModel):
    token: str
    subject: str
    body: str

class CreateFAQBody(BaseModel):
    token: str
    question: str
    answer: str
    order: int = 0
    is_published: bool = True

class UpdateFAQBody(BaseModel):
    token: str
    question: Optional[str] = None
    answer: Optional[str] = None
    order: Optional[int] = None
    is_published: Optional[bool] = None

class UpdateTicketStatusBody(BaseModel):
    token: str
    status: TicketStatus

class ReplyToTicketBody(BaseModel):
    token: str
    message: str


# ── User endpoints ────────────────────────────────────────────────────────────

@router.post("/ticket")
async def submit_ticket(req: SubmitTicketBody):
    user_id = await _decode_token(req.token)

    async with Session() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        ticket = SupportTicket(
            user_id=user_id,
            user_email=user.email,
            subject=req.subject.strip(),
            body=req.body.strip(),
            status=TicketStatus.OPEN,
        )
        db.add(ticket)
        await db.commit()
        await db.refresh(ticket)
        ticket_id = str(ticket.id)
        user_name = f"{user.first_name} {user.last_name}"
        user_email = user.email

    admin_email = settings.SENDER_EMAIL
    html = f"""
    <html><body style="font-family:sans-serif;color:#333;max-width:600px;margin:0 auto;">
    <h2 style="color:#1a1a2e;">New Support Ticket</h2>
    <p><strong>From:</strong> {user_name} (<a href="mailto:{user_email}">{user_email}</a>)</p>
    <p><strong>Subject:</strong> {req.subject}</p>
    <hr style="border:none;border-top:1px solid #eee;"/>
    <div style="background:#f9f9f9;padding:16px;border-radius:8px;margin:16px 0;">
      <p style="margin:0;white-space:pre-wrap;">{req.body}</p>
    </div>
    <hr style="border:none;border-top:1px solid #eee;"/>
    <p style="font-size:12px;color:#888;">Ticket ID: {ticket_id} — Manage via the Admin Dashboard.</p>
    </body></html>
    """
    try:
        await send_email(to_email=admin_email, subject=f"[Support] {req.subject}", body=html)
    except Exception:
        logger.warning("Admin email notification failed", ticket_id=ticket_id)

    return {"message": "Ticket submitted successfully.", "ticket_id": ticket_id, "status_code": 200}


@router.get("/faqs")
async def get_published_faqs():
    async with Session() as db:
        result = await db.execute(
            select(FAQ).where(FAQ.is_published == True).order_by(FAQ.order.asc(), FAQ.created_at.asc())
        )
        faqs = result.scalars().all()
    return {
        "faqs": [
            {"id": str(f.id), "question": f.question, "answer": f.answer, "order": f.order}
            for f in faqs
        ]
    }


# ── Admin FAQ endpoints ───────────────────────────────────────────────────────

@router.get("/admin/faqs")
async def admin_get_faqs(token: str):
    await _verify_admin(token)
    async with Session() as db:
        result = await db.execute(select(FAQ).order_by(FAQ.order.asc(), FAQ.created_at.asc()))
        faqs = result.scalars().all()
    return {
        "faqs": [
            {
                "id": str(f.id),
                "question": f.question,
                "answer": f.answer,
                "order": f.order,
                "is_published": f.is_published,
                "created_at": f.created_at.isoformat() if f.created_at else None,
                "updated_at": f.updated_at.isoformat() if f.updated_at else None,
            }
            for f in faqs
        ]
    }


@router.post("/admin/faqs")
async def admin_create_faq(req: CreateFAQBody):
    await _verify_admin(req.token)
    async with Session() as db:
        faq = FAQ(
            question=req.question.strip(),
            answer=req.answer.strip(),
            order=req.order,
            is_published=req.is_published,
        )
        db.add(faq)
        await db.commit()
        await db.refresh(faq)
    return {"message": "FAQ created.", "id": str(faq.id), "status_code": 200}


@router.put("/admin/faqs/{faq_id}")
async def admin_update_faq(faq_id: str, req: UpdateFAQBody):
    await _verify_admin(req.token)
    async with Session() as db:
        faq = (await db.execute(select(FAQ).where(FAQ.id == faq_id))).scalar_one_or_none()
        if not faq:
            raise HTTPException(status_code=404, detail="FAQ not found.")
        if req.question is not None:
            faq.question = req.question.strip()
        if req.answer is not None:
            faq.answer = req.answer.strip()
        if req.order is not None:
            faq.order = req.order
        if req.is_published is not None:
            faq.is_published = req.is_published
        await db.commit()
    return {"message": "FAQ updated.", "status_code": 200}


@router.delete("/admin/faqs/{faq_id}")
async def admin_delete_faq(faq_id: str, token: str):
    await _verify_admin(token)
    async with Session() as db:
        faq = (await db.execute(select(FAQ).where(FAQ.id == faq_id))).scalar_one_or_none()
        if not faq:
            raise HTTPException(status_code=404, detail="FAQ not found.")
        await db.delete(faq)
        await db.commit()
    return {"message": "FAQ deleted.", "status_code": 200}


# ── Admin ticket endpoints ────────────────────────────────────────────────────

@router.get("/admin/tickets")
async def admin_get_tickets(token: str, status: Optional[str] = None):
    await _verify_admin(token)
    async with Session() as db:
        q = select(SupportTicket).order_by(SupportTicket.created_at.desc())
        if status:
            try:
                q = q.where(SupportTicket.status == TicketStatus[status.upper()])
            except KeyError:
                pass
        result = await db.execute(q)
        tickets = result.scalars().all()
    return {
        "tickets": [
            {
                "id": str(t.id),
                "user_id": str(t.user_id) if t.user_id else None,
                "user_email": t.user_email,
                "subject": t.subject,
                "body": t.body,
                "status": t.status.value,
                "acknowledged": t.acknowledged,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            }
            for t in tickets
        ]
    }


@router.put("/admin/tickets/{ticket_id}/status")
async def admin_update_ticket_status(ticket_id: str, req: UpdateTicketStatusBody):
    await _verify_admin(req.token)
    async with Session() as db:
        ticket = (await db.execute(select(SupportTicket).where(SupportTicket.id == ticket_id))).scalar_one_or_none()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found.")
        old_status = ticket.status
        ticket.status = req.status
        await db.commit()
        subject = ticket.subject
        user_email = ticket.user_email

    if req.status == TicketStatus.RESOLVED and old_status != TicketStatus.RESOLVED:
        html = f"""
        <html><body style="font-family:sans-serif;color:#333;max-width:600px;margin:0 auto;">
        <h2 style="color:#1a1a2e;">Your support ticket has been resolved</h2>
        <p>Hello,</p>
        <p>Your support ticket <strong>"{subject}"</strong> has been marked as <strong>resolved</strong> by our team.</p>
        <p>If you need further assistance, please don't hesitate to reach out again via the BonPlan.ai support page.</p>
        <br/>
        <p>Best,<br/>BonPlan.ai Team</p>
        </body></html>
        """
        try:
            await send_email(to_email=user_email, subject=f"[Resolved] {subject}", body=html)
        except Exception:
            logger.warning("Resolution email failed", ticket_id=ticket_id)

    return {"message": "Status updated.", "status_code": 200}


@router.post("/admin/tickets/{ticket_id}/acknowledge")
async def admin_acknowledge_ticket(ticket_id: str, token: str):
    await _verify_admin(token)
    async with Session() as db:
        ticket = (await db.execute(select(SupportTicket).where(SupportTicket.id == ticket_id))).scalar_one_or_none()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found.")
        if ticket.acknowledged:
            raise HTTPException(status_code=409, detail="Ticket already acknowledged.")
        ticket.acknowledged = True
        await db.commit()
        subject = ticket.subject
        user_email = ticket.user_email

    html = f"""
    <html><body style="font-family:sans-serif;color:#333;max-width:600px;margin:0 auto;">
    <h2 style="color:#1a1a2e;">We received your support request</h2>
    <p>Hello,</p>
    <p>Thanks for reaching out. We've received your ticket regarding <strong>"{subject}"</strong> and our team is on it.</p>
    <p>We'll get back to you as soon as possible. In the meantime, feel free to check our FAQ section on the support page for quick answers.</p>
    <br/>
    <p>Best,<br/>BonPlan.ai Team</p>
    </body></html>
    """
    try:
        await send_email(to_email=user_email, subject=f"[Received] {subject}", body=html)
    except Exception as e:
        logger.error("Acknowledge email failed", ticket_id=ticket_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to send acknowledgement email.")

    return {"message": "Acknowledgement sent.", "status_code": 200}


@router.post("/admin/tickets/{ticket_id}/reply")
async def admin_reply_to_ticket(ticket_id: str, req: ReplyToTicketBody):
    await _verify_admin(req.token)
    async with Session() as db:
        ticket = (await db.execute(select(SupportTicket).where(SupportTicket.id == ticket_id))).scalar_one_or_none()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found.")
        subject = ticket.subject
        user_email = ticket.user_email

    html = f"""
    <html><body style="font-family:sans-serif;color:#333;max-width:600px;margin:0 auto;">
    <h2 style="color:#1a1a2e;">Reply to your support ticket</h2>
    <p>Hello,</p>
    <p>Regarding your ticket <strong>"{subject}"</strong>:</p>
    <hr style="border:none;border-top:1px solid #eee;"/>
    <div style="background:#f9f9f9;padding:16px;border-radius:8px;margin:16px 0;">
      <p style="margin:0;white-space:pre-wrap;">{req.message}</p>
    </div>
    <hr style="border:none;border-top:1px solid #eee;"/>
    <p>If you have more questions, visit the support page or reply to this email.</p>
    <br/>
    <p>Best,<br/>BonPlan.ai Team</p>
    </body></html>
    """
    try:
        await send_email(to_email=user_email, subject=f"Re: {subject}", body=html)
    except Exception as e:
        logger.error("Reply email failed", ticket_id=ticket_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to send reply email.")

    return {"message": "Reply sent.", "status_code": 200}
