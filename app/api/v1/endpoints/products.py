from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
import logging

from app.db.session import get_db
from app.core.auth import require_admin, get_current_user
from app.schemas.schemas import (
    ProductOut, ProductDetailOut, ProductCreate, ProductUpdate,
    PaginatedProducts, ReviewCreate, ReviewOut,
)
from app.models.models import User, Category
from app.db.crud.product import (
    get_products, get_product_by_slug, get_product_by_id,
    create_product, update_product, delete_product, get_featured_products,
)
from app.db.crud.review import (
    get_product_reviews, create_review,
    get_review_by_user_product, get_product_stats,
)
from app.services.search_service import index_product, delete_product_index
from app.services.storage_service import upload_image

router = APIRouter(prefix="/products", tags=["products"])
logger = logging.getLogger(__name__)


@router.get("/categories")
async def list_categories_public(db: AsyncSession = Depends(get_db)):
    """ดึงหมวดหมู่ทั้งหมด — public"""
    result = await db.execute(select(Category).order_by(Category.name))
    cats = result.scalars().all()
    return [{"id": c.id, "name": c.name, "slug": c.slug} for c in cats]


@router.get("", response_model=PaginatedProducts)
async def list_products(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    featured: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
):
    return await get_products(db, page, per_page, category, min_price, max_price, featured)


@router.get("/featured", response_model=List[ProductOut])
async def featured_products(db: AsyncSession = Depends(get_db)):
    return await get_featured_products(db)


# ── Product detail with stats + reviews ─────────────────────────────────────
@router.get("/{slug}", response_model=ProductDetailOut)
async def get_product(slug: str, db: AsyncSession = Depends(get_db)):
    product = await get_product_by_slug(db, slug)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    stats = await get_product_stats(db, product.id)
    raw_reviews = await get_product_reviews(db, product.id)

    reviews_out = []
    for r in raw_reviews:
        # load user name
        user_result = await db.execute(select(User).where(User.id == r.user_id))
        user = user_result.scalar_one_or_none()
        reviews_out.append(ReviewOut(
            id=r.id,
            product_id=r.product_id,
            user_id=r.user_id,
            reviewer_name=user.full_name if user else "ผู้ใช้งาน",
            rating=r.rating,
            title=r.title,
            body=r.body,
            created_at=r.created_at,
        ))

    return ProductDetailOut(
        id=product.id,
        name=product.name,
        slug=product.slug,
        description=product.description,
        price=product.price,
        compare_price=product.compare_price,
        sku=product.sku,
        stock=product.stock,
        weight=product.weight,
        images=product.images,
        attributes=product.attributes,
        how_to=product.how_to or [],
        is_active=product.is_active,
        is_featured=product.is_featured,
        category_id=product.category_id,
        created_at=product.created_at,
        **stats,
        reviews=reviews_out,
    )


# ── Reviews ──────────────────────────────────────────────────────────────────
@router.post("/{product_id}/reviews", response_model=ReviewOut)
async def add_review(
    product_id: str,
    body: ReviewCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = await get_product_by_id(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    existing = await get_review_by_user_product(db, current_user.id, product_id)
    if existing:
        raise HTTPException(status_code=400, detail="คุณรีวิวสินค้านี้ไปแล้ว")

    review = await create_review(db, {
        "product_id": product_id,
        "user_id": current_user.id,
        "rating": body.rating,
        "title": body.title,
        "body": body.body,
    })
    await db.commit()
    await db.refresh(review)

    return ReviewOut(
        id=review.id,
        product_id=review.product_id,
        user_id=review.user_id,
        reviewer_name=current_user.full_name,
        rating=review.rating,
        title=review.title,
        body=review.body,
        created_at=review.created_at,
    )


# ── Admin CRUD ────────────────────────────────────────────────────────────────
@router.post("", response_model=ProductOut)
async def create(
    body: ProductCreate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    product = await create_product(db, body)
    await index_product(product)
    return product


@router.put("/{product_id}", response_model=ProductOut)
async def update(
    product_id: str,
    body: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    product = await update_product(db, product_id, body)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    await index_product(product)
    return product


@router.delete("/{product_id}")
async def delete(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    await delete_product(db, product_id)
    await delete_product_index(product_id)
    return {"message": "Deleted"}


@router.post("/{product_id}/images")
async def upload_product_image(
    product_id: str,
    file: UploadFile = File(...),
    _admin=Depends(require_admin),
):
    url = await upload_image(file, folder=f"products/{product_id}")
    return {"url": url}