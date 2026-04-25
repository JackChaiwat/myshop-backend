from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.models import Order, OrderItem


async def create_order(db: AsyncSession, data: dict) -> Order:
    items_data = data.pop('items', [])
    order = Order(**data)
    db.add(order)
    await db.flush()
    for item in items_data:
        db.add(OrderItem(order_id=order.id, **item))
    await db.flush()

    result = await db.execute(
        select(Order).where(Order.id == order.id).options(selectinload(Order.items))
    )
    return result.scalar_one()


async def get_order(db: AsyncSession, order_id: str) -> Order | None:
    result = await db.execute(
        select(Order).where(Order.id == order_id)
        .options(selectinload(Order.items), selectinload(Order.user))
    )
    return result.scalar_one_or_none()


async def get_user_orders(db: AsyncSession, user_id: str):
    result = await db.execute(
        select(Order).where(Order.user_id == user_id)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
    )
    return result.scalars().all()


async def get_all_orders(db: AsyncSession):
    result = await db.execute(
        select(Order).options(selectinload(Order.items)).order_by(Order.created_at.desc())
    )
    return result.scalars().all()


async def update_order_status(
    db: AsyncSession,
    order_id: str,
    status: str = None,
    payment_status: str = None,
    payment_url: str = None,
    tracking_number: str = None,
) -> Order | None:
    result = await db.execute(
        select(Order).where(Order.id == order_id)
        .options(selectinload(Order.items), selectinload(Order.user))
    )
    order = result.scalar_one_or_none()
    if not order:
        return None
    if status:
        order.status = status
    if payment_status:
        order.payment_status = payment_status
    if payment_url:
        order.payment_url = payment_url
    if tracking_number:
        order.tracking_number = tracking_number
    await db.flush()
    return order
