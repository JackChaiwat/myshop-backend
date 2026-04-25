"""app/api/v1/endpoints/wishlist.py"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from datetime import datetime
from typing import List

from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.models import Wishlist, Product, User
from app.schemas.schemas import ProductOut

router = APIRouter(prefix="/wishlist", tags=["wishlist"])


@router.get("", response_model=List[ProductOut])
async def get_wishlist(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Wishlist)
        .where(Wishlist.user_id == current_user.id)
        .options(selectinload(Wishlist.product))
        .order_by(Wishlist.created_at.desc())
    )
    items = result.scalars().all()
    return [item.product for item in items if item.product]


@router.post("/{product_id}", status_code=201)
async def add_to_wishlist(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Check product exists
    product = await db.get(Product, product_id)
    if not product or not product.is_active:
        raise HTTPException(status_code=404, detail="ไม่พบสินค้า")

    # Check duplicate
    existing = await db.execute(
        select(Wishlist).where(
            Wishlist.user_id == current_user.id,
            Wishlist.product_id == product_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="สินค้านี้อยู่ใน Wishlist แล้ว")

    item = Wishlist(user_id=current_user.id, product_id=product_id, created_at=datetime.utcnow())
    db.add(item)
    await db.commit()
    return {"message": "เพิ่มใน Wishlist แล้ว"}


@router.delete("/{product_id}", status_code=204)
async def remove_from_wishlist(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        delete(Wishlist).where(
            Wishlist.user_id == current_user.id,
            Wishlist.product_id == product_id,
        )
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="ไม่พบสินค้าใน Wishlist")


@router.get("/check/{product_id}")
async def check_wishlist(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Wishlist).where(
            Wishlist.user_id == current_user.id,
            Wishlist.product_id == product_id,
        )
    )
    return {"in_wishlist": result.scalar_one_or_none() is not None}
