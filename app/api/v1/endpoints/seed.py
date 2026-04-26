"""app/api/v1/endpoints/seed.py"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models import User, UserRole
from app.core.auth import hash_password

router = APIRouter(prefix="/seed", tags=["seed"])

@router.post("/admin")
async def seed_admin(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == "admin@example.com"))
    existing = result.scalar_one_or_none()

    if existing:
        return {"message": f"Admin already exists: {existing.email}"}

    admin = User(
        email="admin@example.com",
        hashed_password=hash_password("admin1234"),
        full_name="Admin",
        role=UserRole.admin,       # ✅ ใช้ enum ไม่ใช่ string
        is_active=True,
        is_verified=True,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return {"message": f"Admin created: {admin.email}", "id": admin.id}