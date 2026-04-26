"""app/api/v1/endpoints/seed.py — ใช้ครั้งเดียวแล้วลบ"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import get_password_hash
from app.models.user import User, UserRole

router = APIRouter()

@router.post("/admin")
def seed_admin(db: Session = Depends(get_db)):
    """สร้าง admin user (ใช้ครั้งเดียวแล้วลบ endpoint นี้)"""
    
    admin_email = "admin@example.com"
    
    # ตรวจสอบว่ามี admin อยู่แล้วหรือไม่
    existing_admin = db.query(User).filter(User.email == admin_email).first()
    
    if existing_admin:
        return {
            "message": "Admin user already exists",
            "email": existing_admin.email,
            "role": existing_admin.role.value if existing_admin.role else None
        }
    
    # สร้าง admin user
    try:
        admin_user = User(
            email=admin_email,
            hashed_password=get_password_hash("admin1234"),
            full_name="System Administrator",
            phone="0812345678",  # ใส่เบอร์โทร หรือจะไม่ใส่ก็ได้
            role=UserRole.admin,  # สำคัญ: ใช้ enum value
            is_active=True,
            is_verified=True
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        return {
            "message": "Admin user created successfully",
            "email": admin_user.email,
            "full_name": admin_user.full_name,
            "role": admin_user.role.value,
            "password": "admin1234"  # เอาไว้ใช้ login
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))