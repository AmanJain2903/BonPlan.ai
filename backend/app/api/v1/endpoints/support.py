# backend/app/api/v1/endpoints/support.py

from typing import Optional
import html as html_lib

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
from app.utils.emailVerification import SUPPORT_EMAIL_ADDRESS, SUPPORT_EMAIL_FROM, bonplan_inline_images, render_email_layout, send_email

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

    admin_email = SUPPORT_EMAIL_ADDRESS
    safe_subject = html_lib.escape(req.subject)
    safe_body = html_lib.escape(req.body)
    safe_user_name = html_lib.escape(user_name.strip() or user_email)
    safe_user_email = html_lib.escape(user_email)
    html = render_email_layout(
        title="New support ticket",
        preheader=f"New ticket from {safe_user_name}: {safe_subject}",
        eyebrow="Support",
        body_html=f"""
        <p style="margin:0 0 12px;"><strong style="color:#ffffff;">From:</strong> {safe_user_name} ({safe_user_email})</p>
        <p style="margin:0 0 18px;"><strong style="color:#ffffff;">Subject:</strong> {safe_subject}</p>
        <div style="background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.08);padding:16px;border-radius:12px;margin:16px 0;">
          <p style="margin:0;white-space:pre-wrap;">{safe_body}</p>
        </div>
        <p style="font-size:13px;color:rgba(197,198,199,0.72);margin:0;">Ticket ID: {html_lib.escape(ticket_id)}. Manage this from the Admin Dashboard.</p>
        """,
        footer_html="Support notifications are sent from support@bonplanai.com.",
    )
    try:
        await send_email(to_email=admin_email, subject=f"[Support] {req.subject}", body=html, from_email=SUPPORT_EMAIL_FROM, inline_images=bonplan_inline_images())
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
        safe_subject = html_lib.escape(subject)
        html = render_email_layout(
            title="Your support ticket is resolved",
            preheader=f"Your ticket {safe_subject} has been resolved.",
            eyebrow="Support",
            body_html=f"""
            <p style="margin:0 0 14px;">Hello,</p>
            <p style="margin:0 0 16px;">Your support ticket <strong style="color:#ffffff;">{safe_subject}</strong> has been marked as resolved by our team.</p>
            <p style="margin:0 0 18px;">If you need more help, reach out again from the BonPlan.ai support page or reply to this email.</p>
            """,
            footer_html="Support emails are sent from support@bonplanai.com.",
        )
        try:
            await send_email(to_email=user_email, subject=f"[Resolved] {subject}", body=html, from_email=SUPPORT_EMAIL_FROM, inline_images=bonplan_inline_images())
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

    safe_subject = html_lib.escape(subject)
    html = render_email_layout(
        title="We received your support request",
        preheader=f"We received your ticket about {safe_subject}.",
        eyebrow="Support",
        body_html=f"""
        <p style="margin:0 0 14px;">Hello,</p>
        <p style="margin:0 0 16px;">Thanks for reaching out. We received your ticket regarding <strong style="color:#ffffff;">{safe_subject}</strong> and our team is on it.</p>
        <p style="margin:0 0 18px;">We will get back to you as soon as possible.</p>
        """,
        footer_html="Support emails are sent from support@bonplanai.com.",
    )
    try:
        await send_email(to_email=user_email, subject=f"[Received] {subject}", body=html, from_email=SUPPORT_EMAIL_FROM, inline_images=bonplan_inline_images())
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

    safe_subject = html_lib.escape(subject)
    safe_message = html_lib.escape(req.message)
    html = render_email_layout(
        title="Reply to your support ticket",
        preheader=f"BonPlan.ai support replied to {safe_subject}.",
        eyebrow="Support",
        body_html=f"""
        <p style="margin:0 0 14px;">Hello,</p>
        <p style="margin:0 0 16px;">Regarding your ticket <strong style="color:#ffffff;">{safe_subject}</strong>:</p>
        <div style="background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.08);padding:16px;border-radius:12px;margin:16px 0;">
          <p style="margin:0;white-space:pre-wrap;">{safe_message}</p>
        </div>
        <p style="margin:0 0 18px;">If you have more questions, visit the support page or reply to this email.</p>
        """,
        footer_html="Support emails are sent from support@bonplanai.com.",
    )
    try:
        await send_email(to_email=user_email, subject=f"Re: {subject}", body=html, from_email=SUPPORT_EMAIL_FROM, inline_images=bonplan_inline_images())
    except Exception as e:
        logger.error("Reply email failed", ticket_id=ticket_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to send reply email.")

    return {"message": "Reply sent.", "status_code": 200}
