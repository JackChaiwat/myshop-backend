"""app/api/v1/endpoints/seed.py — ใช้ครั้งเดียวแล้วลบ"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import get_password_hash
from app.models.user import User

router = APIRouter()

@router.post("/admin")
def seed_admin(db: Session = Depends(get_db)):
    """สร้าง admin user (ใช้ครั้งเดียวแล้วลบ endpoint นี้)"""
    admin_email = "admin@example.com"
    admin_username = "admin"
    
   
    existing_admin = db.query(User).filter(
        (User.email == admin_email) | (User.username == admin_username)
    ).first()
    
    if existing_admin:
        return {
            "message": "Admin user already exists",
            "email": existing_admin.email,
            "username": existing_admin.username
        }
    
    
    admin_user = User(
        email=admin_email,
        username=admin_username,
        hashed_password=get_password_hash("admin1234"),  
        full_name="Administrator",
        role="admin",
        is_active=True,
        is_verified=True
    )
    
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    
    return {
        "message": "Admin user created successfully",
        "email": admin_user.email,
        "username": admin_user.username,
        "password": "admin1234"  
    }