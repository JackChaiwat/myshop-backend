"""app/api/v1/endpoints/verification.py
OTP-based email & phone verification
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
import secrets
import logging

from app.db.session import get_db
from app.core.auth import get_current_user
from app.core.limiter import limiter
from fastapi import Request
from app.models.models import OTPCode, User
from app.db.crud.user import update_user
from app.services.email_service import send_otp_email
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/verify", tags=["verification"])
logger = logging.getLogger(__name__)

OTP_EXPIRE_MINUTES = 10


def _gen_otp() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(6))


async def _create_otp(db: AsyncSession, user_id: str, purpose: str) -> str:
    code = _gen_otp()
    otp = OTPCode(
        user_id=user_id,
        code=code,
        purpose=purpose,
        expires_at=datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES),
        created_at=datetime.utcnow(),
    )
    db.add(otp)
    await db.flush()
    return code


# ─── Email Verification ───────────────────────────────────

@router.post("/email/send")
@limiter.limit("3/minute")
async def send_email_otp(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.is_verified:
        raise HTTPException(status_code=400, detail="อีเมลนี้ยืนยันแล้ว")

    code = await _create_otp(db, current_user.id, "email_verify")
    await db.commit()

    await send_otp_email(current_user.email, current_user.full_name, code)
    return {"message": f"ส่ง OTP ไปที่ {current_user.email} แล้ว (หมดอายุใน {OTP_EXPIRE_MINUTES} นาที)"}


class OTPVerifyRequest(BaseModel):
    code: str


@router.post("/email/confirm")
async def confirm_email_otp(
    body: OTPVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(OTPCode).where(
            OTPCode.user_id == current_user.id,
            OTPCode.purpose == "email_verify",
            OTPCode.is_used == False,
            OTPCode.expires_at > datetime.utcnow(),
        ).order_by(OTPCode.created_at.desc()).limit(1)
    )
    otp = result.scalar_one_or_none()

    if not otp or otp.code != body.code:
        raise HTTPException(status_code=400, detail="รหัส OTP ไม่ถูกต้องหรือหมดอายุ")

    otp.is_used = True
    await update_user(db, current_user.id, {"is_verified": True})
    await db.commit()
    return {"message": "ยืนยันอีเมลสำเร็จ"}


# ─── Phone Update ─────────────────────────────────────────

class PhoneUpdateRequest(BaseModel):
    phone: str


@router.put("/phone")
async def update_phone(
    body: PhoneUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """อัปเดตเบอร์โทรศัพท์ (ไม่มี OTP สำหรับเบอร์โทร — เปลี่ยนได้ทันที)"""
    phone = body.phone.strip()
    if not phone:
        raise HTTPException(status_code=400, detail="กรุณากรอกเบอร์โทร")
    user = await update_user(db, current_user.id, {"phone": phone})
    await db.commit()
    return {"message": "อัปเดตเบอร์โทรแล้ว", "phone": user.phone}


# ─── Email Change ─────────────────────────────────────────

class EmailChangeRequest(BaseModel):
    new_email: EmailStr


@router.post("/email/change/send")
@limiter.limit("3/minute")
async def send_email_change_otp(
    request: Request,
    body: EmailChangeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ขอเปลี่ยนอีเมล — ส่ง OTP ไปที่อีเมลใหม่"""
    from app.db.crud.user import get_user_by_email
    existing = await get_user_by_email(db, body.new_email)
    if existing:
        raise HTTPException(status_code=400, detail="อีเมลนี้ถูกใช้งานแล้ว")

    code = await _create_otp(db, current_user.id, f"email_change:{body.new_email}")
    await db.commit()

    await send_otp_email(body.new_email, current_user.full_name, code)
    return {"message": f"ส่ง OTP ไปที่ {body.new_email} แล้ว"}


class EmailChangeConfirmRequest(BaseModel):
    new_email: EmailStr
    code: str


@router.post("/email/change/confirm")
async def confirm_email_change(
    body: EmailChangeConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(OTPCode).where(
            OTPCode.user_id == current_user.id,
            OTPCode.purpose == f"email_change:{body.new_email}",
            OTPCode.is_used == False,
            OTPCode.expires_at > datetime.utcnow(),
        ).order_by(OTPCode.created_at.desc())
    )
    otp = result.scalar_one_or_none()
    if not otp or otp.code != body.code:
        raise HTTPException(status_code=400, detail="รหัส OTP ไม่ถูกต้องหรือหมดอายุ")

    otp.is_used = True
    await update_user(db, current_user.id, {"email": body.new_email, "is_verified": True})
    await db.commit()
    return {"message": "เปลี่ยนอีเมลสำเร็จ"}