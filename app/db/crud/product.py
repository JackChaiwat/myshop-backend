from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from app.models.models import Product
from app.schemas.schemas import ProductCreate, ProductUpdate, PaginatedProducts
import re, uuid


def slugify(text: str) -> str:
    # For Thai/non-ASCII text, use UUID-based slug
    ascii_text = re.sub(r'[^\x00-\x7F]', '', text).strip()
    if len(ascii_text) < 3:
        return str(uuid.uuid4())[:8]
    slug = ascii_text.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_-]+', '-', slug)
    return slug or str(uuid.uuid4())[:8]


async def get_products(
    db: AsyncSession,
    page: int = 1,
    per_page: int = 20,
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    featured: Optional[bool] = None,
) -> PaginatedProducts:
    q = select(Product).where(Product.is_active == True)
    if category:
        q = q.where(Product.category_id == category)
    if min_price is not None:
        q = q.where(Product.price >= min_price)
    if max_price is not None:
        q = q.where(Product.price <= max_price)
    if featured is not None:
        q = q.where(Product.is_featured == featured)

    total_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar_one()

    q = q.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(q)
    items = result.scalars().all()

    return PaginatedProducts(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=max(1, (total + per_page - 1) // per_page),
    )


async def get_product_by_slug(db: AsyncSession, slug: str) -> Product | None:
    result = await db.execute(select(Product).where(Product.slug == slug))
    return result.scalar_one_or_none()


async def get_product_by_id(db: AsyncSession, product_id: str) -> Product | None:
    result = await db.execute(select(Product).where(Product.id == product_id))
    return result.scalar_one_or_none()


async def get_featured_products(db: AsyncSession, limit: int = 8):
    result = await db.execute(
        select(Product).where(Product.is_featured == True, Product.is_active == True).limit(limit)
    )
    return result.scalars().all()


async def create_product(db: AsyncSession, data: ProductCreate) -> Product:
    base_slug = slugify(data.name)
    slug = base_slug
    # Ensure unique slug
    counter = 1
    while True:
        existing = await get_product_by_slug(db, slug)
        if not existing:
            break
        slug = f"{base_slug}-{counter}"
        counter += 1

    product = Product(**data.model_dump(), slug=slug)
    db.add(product)
    await db.flush()
    await db.refresh(product)
    return product


async def update_product(db: AsyncSession, product_id: str, data: ProductUpdate) -> Product | None:
    product = await get_product_by_id(db, product_id)
    if not product:
        return None
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(product, k, v)
    await db.flush()
    await db.refresh(product)
    return product


async def delete_product(db: AsyncSession, product_id: str):
    product = await get_product_by_id(db, product_id)
    if product:
        await db.delete(product)
        await db.flush()


async def update_stock(db: AsyncSession, product_id: str, delta: int):
    product = await get_product_by_id(db, product_id)
    if product:
        product.stock = max(0, product.stock + delta)
        await db.flush()
