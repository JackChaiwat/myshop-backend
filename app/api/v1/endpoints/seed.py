"""app/api/v1/endpoints/seed.py — ใช้ครั้งเดียวแล้วลบ"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.crud.user import create_user
from app.core.auth import hash_password

router = APIRouter(prefix="/seed", tags=["seed"])

@router.post("/admin")
async def seed_admin(db: AsyncSession = Depends(get_db)):
    try:
        user = await create_user(db, {
            'email': 'admin@example.com',
            'hashed_password': hash_password('admin1234'),
            'full_name': 'Admin',
            'role': 'admin',
            'is_verified': True,
        })
        await db.commit()
        return {"message": f"Admin created: {user.email}"}
    except Exception as e:
        return {"message": f"Error (maybe already exists): {str(e)}"}