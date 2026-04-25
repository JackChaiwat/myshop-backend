"""app/api/v1/endpoints/users.py"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid
from pathlib import Path
from PIL import Image
import io

from app.db.session import get_db
from app.core.auth import get_current_user, hash_password, verify_password
from app.schemas.schemas import (
    AddressCreate,
    AddressOut,
    AddressUpdate,
    ChangePasswordRequest,
    UserOut,
)
from app.db.crud.address import (
    get_user_addresses,
    create_address,
    update_address,
    delete_address,
    set_default_address,
)
from app.db.crud.user import update_user
from app.models.models import User

router = APIRouter(prefix="/users", tags=["users"])

# ─── Config ───────────────────────────────────────────────────────────────────

UPLOAD_DIR = Path("static/avatars")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_SIZE_MB = 5
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}

# ─── Helper ───────────────────────────────────────────────────────────────────

def _crop_center(img: Image.Image) -> Image.Image:
    """Crop รูปให้เป็นสี่เหลี่ยมจัตุรัสตรงกลาง"""
    w, h = img.size
    min_side = min(w, h)
    left = (w - min_side) // 2
    top = (h - min_side) // 2
    return img.crop((left, top, left + min_side, top + min_side))

# ─── Profile ──────────────────────────────────────────────────────────────────

@router.put("/me", response_model=UserOut)
async def update_me(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    allowed = {k: v for k, v in body.items() if k in ("full_name", "phone")}
    return await update_user(db, current_user.id, allowed)

# ─── Change Password ──────────────────────────────────────────────────────────

@router.post("/me/change-password")
async def change_password(
    body: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """เปลี่ยนรหัสผ่าน — ต้องใส่รหัสเก่าให้ถูกต้องก่อน"""
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="รหัสผ่านปัจจุบันไม่ถูกต้อง")
    await update_user(db, current_user.id, {"hashed_password": hash_password(body.new_password)})
    return {"message": "เปลี่ยนรหัสผ่านสำเร็จ"}

# ─── Avatar ───────────────────────────────────────────────────────────────────

@router.post("/me/avatar", response_model=UserOut)
async def upload_avatar(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """อัปโหลดรูปโปรไฟล์ — รองรับ JPEG / PNG / WebP ขนาดไม่เกิน 5MB"""
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="รองรับเฉพาะ JPEG, PNG, WebP")

    contents = await file.read()
    if len(contents) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"ไฟล์ต้องไม่เกิน {MAX_SIZE_MB}MB")

    img = Image.open(io.BytesIO(contents)).convert("RGB")
    img = _crop_center(img).resize((256, 256), Image.LANCZOS)

    # ลบ avatar เก่า
    if current_user.avatar_url:
        old_path = Path("." + current_user.avatar_url)
        if old_path.exists():
            old_path.unlink()

    filename = f"{uuid.uuid4().hex}.webp"
    # uuid.hex ผลิตตัวอักษร hex เท่านั้น ไม่มี path traversal แต่ validate ไว้เป็น defense-in-depth
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    img.save(UPLOAD_DIR / filename, "WEBP", quality=85)

    return await update_user(db, current_user.id, {"avatar_url": f"/static/avatars/{filename}"})


@router.delete("/me/avatar", response_model=UserOut)
async def delete_avatar(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ลบรูปโปรไฟล์ กลับเป็น avatar ตัวอักษร"""
    if current_user.avatar_url:
        old_path = Path("." + current_user.avatar_url)
        if old_path.exists():
            old_path.unlink()
    return await update_user(db, current_user.id, {"avatar_url": None})

# ─── Addresses ────────────────────────────────────────────────────────────────

@router.get("/addresses", response_model=List[AddressOut])
async def list_addresses(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_user_addresses(db, current_user.id)


@router.post("/addresses", response_model=AddressOut, status_code=201)
async def add_address(
    body: AddressCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await create_address(db, current_user.id, body.model_dump())


@router.put("/addresses/{address_id}", response_model=AddressOut)
async def edit_address(
    address_id: str,
    body: AddressUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    address = await update_address(
        db, address_id, current_user.id, body.model_dump(exclude_none=True)
    )
    if not address:
        raise HTTPException(status_code=404, detail="ไม่พบที่อยู่นี้")
    return address


@router.delete("/addresses/{address_id}", status_code=204)
async def remove_address(
    address_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = await delete_address(db, address_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="ไม่พบที่อยู่นี้")


@router.patch("/addresses/{address_id}/default", response_model=AddressOut)
async def set_address_as_default(
    address_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    address = await set_default_address(db, address_id, current_user.id)
    if not address:
        raise HTTPException(status_code=404, detail="ไม่พบที่อยู่นี้")
    return address