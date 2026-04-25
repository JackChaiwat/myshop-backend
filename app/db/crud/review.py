from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.models import Review, OrderItem, Order


async def get_product_reviews(db: AsyncSession, product_id: str) -> list[Review]:
    result = await db.execute(
        select(Review)
        .where(Review.product_id == product_id)
        .order_by(Review.created_at.desc())
    )
    return result.scalars().all()


async def create_review(db: AsyncSession, data: dict) -> Review:
    review = Review(**data)
    db.add(review)
    await db.flush()
    await db.refresh(review)
    return review


async def get_review_by_user_product(db: AsyncSession, user_id: str, product_id: str) -> Review | None:
    result = await db.execute(
        select(Review).where(Review.user_id == user_id, Review.product_id == product_id)
    )
    return result.scalar_one_or_none()


async def get_product_stats(db: AsyncSession, product_id: str) -> dict:
    """Return avg_rating, review_count, sold_count for a product."""
    # Rating stats
    rating_result = await db.execute(
        select(func.avg(Review.rating), func.count(Review.id))
        .where(Review.product_id == product_id)
    )
    avg_rating, review_count = rating_result.one()

    # Sold count from delivered/paid orders
    sold_result = await db.execute(
        select(func.coalesce(func.sum(OrderItem.quantity), 0))
        .join(Order, OrderItem.order_id == Order.id)
        .where(
            OrderItem.product_id == product_id,
            Order.payment_status == "paid",
        )
    )
    sold_count = sold_result.scalar_one()

    return {
        "avg_rating": round(float(avg_rating or 0), 1),
        "review_count": review_count or 0,
        "sold_count": int(sold_count or 0),
    }
