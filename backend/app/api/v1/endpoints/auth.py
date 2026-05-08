# backend/app/api/v1/endpoints/auth.py

"""

This file contains the authentication endpoints for the v1 version of the API.
"""

import asyncio
import bcrypt
import html
import jwt
import re

from datetime import datetime, timezone, timedelta

from fastapi import HTTPException, APIRouter
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.database import Session
from app.database.models.usersTable import User
from app.database.schemas.preferences import TripPreferencesSchema
from app.utils.emailVerification import bonplan_inline_images, render_email_layout, send_email

from app.logging import get_api_logger

logger = get_api_logger("api.auth")

router = APIRouter()


class UpdateProfileRequest(BaseModel):
    token: str
    first_name: str
    last_name: str
    country_code: str | None = None
    phone: str | None = None
    preferences: dict = {}


"""
Helper functions
"""
# Email must be a valid email address
def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

# Password must be at least 8 characters long and contain at least one uppercase letter, one lowercase letter, one special character and one number
def is_valid_password(password):
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", password):
        return False
    return True

def makeFirstLetterCapital(string):
    return string.capitalize()


async def _hash_password(password: str) -> str:
    """bcrypt.hashpw is CPU-bound (hundreds of ms); offload to a thread."""
    hashed = await asyncio.to_thread(
        bcrypt.hashpw, password.encode("utf-8"), bcrypt.gensalt()
    )
    return hashed.decode("utf-8")


async def _check_password(password: str, password_hash: str) -> bool:
    return await asyncio.to_thread(
        bcrypt.checkpw, password.encode("utf-8"), password_hash.encode("utf-8")
    )


async def _send_verification_email_for_user(email: str, db: AsyncSession) -> None:
    """Build and send a verification email using the provided session.

    Does not open its own session and does not commit. Caller supplies the
    already-open session.
    """
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Please register first.")

    tokenPayload = {
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    token = jwt.encode(tokenPayload, settings.SECRET_KEY, algorithm="HS256")
    verificationLink = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    subject = "BonPlan.ai - Verify your email address"
    htmlContent = render_email_layout(
        title="Verify your email address",
        preheader="Confirm your BonPlan.ai account email.",
        eyebrow="Account security",
        body_html=f"""
        <p style="margin:0 0 14px;">Hello {html.escape(user.first_name or "there")},</p>
        <p style="margin:0 0 16px;">Thank you for registering with BonPlan.ai. Verify your email address to finish setting up your account.</p>
        <p style="margin:0 0 18px;color:rgba(214,216,218,0.82);">This link expires in 15 minutes. If you did not request this verification, you can ignore this email.</p>
        """,
        cta_label="Verify Email",
        cta_url=verificationLink,
        footer_html="BonPlan.ai account emails are sent from noreply-auth@bonplanai.com.",
    )
    await send_email(email, subject, htmlContent, inline_images=bonplan_inline_images())


"""
Google authentication endpoint
"""
@router.post("/google", response_model=dict)
async def google_login(token: str):
    if not token:
        raise HTTPException(status_code=400, detail="Token is required.")

    try:
        id_info = await asyncio.to_thread(
            id_token.verify_oauth2_token,
            token,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired Google token.")

    email = id_info.get("email")
    first_name = id_info.get("given_name")
    last_name = id_info.get("family_name", "")

    if not email:
        raise HTTPException(status_code=400, detail="Google account has no email address.")
    if not first_name:
        raise HTTPException(status_code=400, detail="Google account has no first name.")

    async with Session() as db:
        existingUser = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if existingUser and existingUser.auth_provider == "local":
            raise HTTPException(status_code=400, detail="An account with this email already exists. Please log in with your password.")
        elif existingUser and existingUser.auth_provider == "google":
            existingUser.is_new_user = False
            await db.commit()
            token_payload = {
                "user_id": str(existingUser.id),
                "exp": datetime.now(timezone.utc) + timedelta(days=7)
            }
            jwtToken = jwt.encode(token_payload, settings.SECRET_KEY, algorithm="HS256")
            prefs = existingUser.preferences or TripPreferencesSchema().model_dump()
            return {"message": "Login successful", "status_code": 200, "token": jwtToken, "token_type": "Bearer", "first_name": existingUser.first_name, "last_name": existingUser.last_name, "email": existingUser.email, "preferences": prefs, "is_new_user": existingUser.is_new_user, "is_admin": existingUser.is_admin}
        else:
            try:
                newUser = User(
                    first_name=makeFirstLetterCapital(first_name),
                    last_name=makeFirstLetterCapital(last_name),
                    email=email,
                    phone={'country_code': None, 'number': None},
                    auth_provider="google",
                    is_verified=True,
                    preferences=TripPreferencesSchema().model_dump(),
                )
                db.add(newUser)
                await db.commit()
                await db.refresh(newUser)
                token_payload = {
                    "user_id": str(newUser.id),
                    "exp": datetime.now(timezone.utc) + timedelta(days=7)
                }
                jwtToken = jwt.encode(token_payload, settings.SECRET_KEY, algorithm="HS256")
                return {"message": "Registration successful.", "status_code": 201, "token": jwtToken, "token_type": "Bearer", "first_name": newUser.first_name, "last_name": newUser.last_name, "email": newUser.email, "preferences": newUser.preferences, "is_new_user": True, "is_admin": newUser.is_admin}
            except Exception as e:
                logger.error("Failed to create/login a google user", error=str(e))
                await db.rollback()
                raise HTTPException(status_code=500, detail=f"Failed to create user: {e}")


"""
Local registration endpoint
"""
@router.post("/register", response_model=dict)
async def local_register(first_name: str, last_name: str, email: str, password: str, code: str = "", phone: str = ""):
    if not first_name or not last_name or not email or not password:
        missingField = "email" if not email else "password" if not password else "first_name" if not first_name else "last_name"
        raise HTTPException(status_code=400, detail=f"Missing required field: {missingField}")

    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email address. Please enter a valid email address.")

    if not is_valid_password(password):
        raise HTTPException(status_code=400, detail="Invalid password. Please enter a valid password.")

    async with Session() as db:
        existingUser = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if existingUser and existingUser.auth_provider == "local":
            raise HTTPException(status_code=400, detail="User already exists. Please log in.")
        elif existingUser and existingUser.auth_provider == "google":
            raise HTTPException(status_code=400, detail="User already exists. Please log in with Google.")

        phone_json = {'country_code': code if code else None, 'number': phone if phone else None}
        if phone_json['country_code'] and phone_json['number']:
            isPhoneNumberUnique = (await db.execute(
                select(User).where(User.phone == phone_json)
            )).scalar_one_or_none()
            if isPhoneNumberUnique:
                raise HTTPException(status_code=400, detail="Phone number already in use. Please use a different phone number.")

        try:
            password_hash = await _hash_password(password)
            newUser = User(
                first_name=makeFirstLetterCapital(first_name),
                last_name=makeFirstLetterCapital(last_name),
                email=email,
                phone=phone_json,
                password_hash=password_hash,
                auth_provider="local",
                is_verified=False,
                preferences=TripPreferencesSchema().model_dump()
            )
            db.add(newUser)
            await db.commit()
            await _send_verification_email_for_user(email, db)
            return {"message": "Registration successful. A verification email has been sent to your email address. Please verify your email address to login.", "status_code": 201}
        except IntegrityError:
            await db.rollback()
            raise HTTPException(status_code=400, detail="Phone number already in use. Please use a different phone number.")
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Failed to create user", error=str(e))
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to create user: {e}")


"""
Local Login endpoint
"""
@router.post("/login", response_model=dict)
async def local_login(email: str, password: str):
    if not email or not password:
        missingField = "email" if not email else "password"
        raise HTTPException(status_code=400, detail=f"Missing required field: {missingField}")
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email address. Please enter a valid email address.")

    async with Session() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found. Please register first.")
        if user.auth_provider != "local":
            raise HTTPException(status_code=400, detail="This account uses Google sign-in. Please log in with Google.")
        if not await _check_password(password, user.password_hash):
            raise HTTPException(status_code=400, detail="Incorrect password. Please try again.")
        if not user.is_verified:
            await _send_verification_email_for_user(email, db)
            raise HTTPException(status_code=403, detail="User not verified. A verification email has been sent to your email address. Please verify your email address to login.")
        try:
            is_new = user.is_new_user
            user.is_new_user = False
            await db.commit()
            token_payload = {
                "user_id": str(user.id),
                "exp": datetime.now(timezone.utc) + timedelta(days=7)
            }
            jwtToken = jwt.encode(token_payload, settings.SECRET_KEY, algorithm="HS256")
            prefs = user.preferences or TripPreferencesSchema().model_dump()
            return {"message": "Login successful", "status_code": 200, "token": jwtToken, "token_type": "Bearer", "first_name": user.first_name, "last_name": user.last_name, "email": user.email, "preferences": prefs, "is_new_user": is_new, "is_admin": user.is_admin}
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Failed to login a local user", error=str(e))
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to login: {e}")


"""
User Verification endpoints
"""
@router.post("/send-verification-email", response_model=dict)
async def send_verification_email(email: str):
    if not email:
        raise HTTPException(status_code=400, detail="Email is required.")
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email address. Please enter a valid email address.")

    async with Session() as db:
        try:
            await _send_verification_email_for_user(email, db)
            return {"message": "Verification email sent successfully", "status_code": 200}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to send verification email: {e}")


@router.post("/verify-email", response_model=dict)
async def verify_email(token: str):
    try:
        token_payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Verification link has expired. Please request a new one.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid verification link.")
    email = token_payload.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Invalid verification link.")

    async with Session() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        if user.is_verified == True:
            raise HTTPException(status_code=400, detail="Email already verified.")
        try:
            user.is_verified = True
            await db.commit()
            return {"message": "Email verified successfully", "status_code": 200}
        except Exception as e:
            logger.error("Failed to verify email", error=str(e))
            await db.rollback()
            raise HTTPException(status_code=500, detail="Failed to verify email.")


"""
Forgot Password — sends a reset link to the user's email
"""
@router.post("/forgot-password", response_model=dict)
async def forgot_password(email: str):
    if not email:
        raise HTTPException(status_code=400, detail="Email is required.")
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email address.")

    async with Session() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if not user:
            return {"message": "If an account with that email exists, a reset link has been sent.", "status_code": 200}
        if user.auth_provider != "local":
            raise HTTPException(status_code=400, detail="This account uses Google sign-in. Password reset is not available.")

        tokenPayload = {
            "email": email,
            "purpose": "password_reset",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        }
        token = jwt.encode(tokenPayload, settings.SECRET_KEY, algorithm="HS256")
        resetLink = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        subject = "BonPlan.ai - Reset your password"
        htmlContent = render_email_layout(
            title="Reset your password",
            preheader="Use this secure link to reset your BonPlan.ai password.",
            eyebrow="Account security",
            body_html=f"""
            <p style="margin:0 0 14px;">Hello {html.escape(user.first_name or "there")},</p>
            <p style="margin:0 0 16px;">We received a request to reset your password. Use the button below to set a new password.</p>
            <p style="margin:0 0 18px;color:rgba(214,216,218,0.82);">This link expires in 15 minutes. If you did not request this, you can ignore this email.</p>
            """,
            cta_label="Reset Password",
            cta_url=resetLink,
            footer_html="BonPlan.ai account emails are sent from noreply-auth@bonplanai.com.",
        )
        try:
            await send_email(email, subject, htmlContent, inline_images=bonplan_inline_images())
        except Exception as e:
            logger.error("Failed to send password reset email", error=str(e))
            raise HTTPException(status_code=500, detail="Failed to send reset email. Please try again later.")
        return {"message": "If an account with that email exists, a reset link has been sent.", "status_code": 200}


"""
Reset Password — validates the reset token and sets a new password
"""
@router.post("/reset-password", response_model=dict)
async def reset_password(token: str, new_password: str):
    if not token or not new_password:
        raise HTTPException(status_code=400, detail="All fields are required.")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Reset link has expired. Please request a new one.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid reset link.")
    if payload.get("purpose") != "password_reset":
        raise HTTPException(status_code=400, detail="Invalid reset link.")
    email = payload.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Invalid reset link.")
    if not is_valid_password(new_password):
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters with one uppercase, one lowercase, one number, and one special character.")

    async with Session() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        if user.auth_provider != "local":
            raise HTTPException(status_code=400, detail="Password reset is not available for Google accounts.")
        try:
            user.password_hash = await _hash_password(new_password)
            await db.commit()
            return {"message": "Password has been reset successfully. You can now log in.", "status_code": 200}
        except Exception as e:
            logger.error("Failed to reset password", error=str(e))
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to reset password: {e}")


"""
Get Profile endpoint — returns user profile data
"""
@router.get("/profile", response_model=dict)
async def get_profile(token: str):
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

    async with Session() as db:
        try:
            user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
            if not user:
                raise HTTPException(status_code=404, detail="User not found.")
            phone = user.phone or {}
            prefs = user.preferences or TripPreferencesSchema().model_dump()
            return {
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "country_code": phone.get("country_code", ""),
                "phone": phone.get("number", ""),
                "auth_provider": user.auth_provider,
                "preferences": prefs,
                "status_code": 200,
            }
        except Exception as e:
            logger.error(f"Failed to get profile for user: {user_id}", error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to get profile: {e}")


"""
Update Profile endpoint — updates editable user fields
"""
@router.post("/profile", response_model=dict)
async def update_profile(req: UpdateProfileRequest):
    token = req.token
    first_name = req.first_name
    last_name = req.last_name
    country_code = req.country_code
    phone = req.phone
    preferences = req.preferences

    if not token:
        raise HTTPException(status_code=400, detail="Token is required.")
    if not first_name or not last_name:
        raise HTTPException(status_code=400, detail="First name and last name are required.")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session. Please log in again.")
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid token.")

    async with Session() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        try:
            user.first_name = makeFirstLetterCapital(first_name.strip())
            user.last_name = makeFirstLetterCapital(last_name.strip())
            user.phone = {"country_code": country_code.strip() if country_code else None, "number": phone.strip() if phone else None}
            user.preferences = preferences if preferences else user.preferences
            await db.commit()
            return {
                "message": "Profile updated successfully.",
                "first_name": user.first_name,
                "last_name": user.last_name,
                "country_code": (user.phone or {}).get("country_code", ""),
                "phone": (user.phone or {}).get("number", ""),
                "preferences": user.preferences,
                "status_code": 200,
            }
        except IntegrityError:
            await db.rollback()
            raise HTTPException(status_code=400, detail="Phone number already in use. Please use a different phone number.")
        except Exception as e:
            logger.error("Failed to update a user's profile", error=str(e))
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to update profile: {e}")


"""
Change Password endpoint — local users only
"""
@router.post("/change-password", response_model=dict)
async def change_password(token: str, current_password: str, new_password: str):
    if not token or not current_password or not new_password:
        raise HTTPException(status_code=400, detail="All fields are required.")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session. Please log in again.")
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid token.")

    async with Session() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        if user.auth_provider != "local":
            raise HTTPException(status_code=400, detail="Password change is not available for Google accounts.")
        if not await _check_password(current_password, user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect.")
        if not is_valid_password(new_password):
            raise HTTPException(status_code=400, detail="New password must be at least 8 characters with one uppercase, one lowercase, one number, and one special character.")
        if current_password == new_password:
            raise HTTPException(status_code=400, detail="New password must be different from the current password.")
        try:
            user.password_hash = await _hash_password(new_password)
            await db.commit()
            return {"message": "Password changed successfully.", "status_code": 200}
        except Exception as e:
            logger.error("Failed to change a user's password", error=str(e))
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to change password: {e}")


"""
User Delete endpoint — works for both local and Google users via JWT
"""
@router.post("/delete", response_model=dict)
async def delete_user(token: str):
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

    async with Session() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        try:
            await db.delete(user)
            await db.commit()
            return {"message": "Account deleted successfully", "status_code": 200}
        except Exception as e:
            logger.error("Failed to delete a user's account", error=str(e))
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to delete account: {e}")
