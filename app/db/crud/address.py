"""db/crud/address.py"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.models import Address


async def get_address(db: AsyncSession, address_id: str, user_id: str) -> Address | None:
    result = await db.execute(
        select(Address).where(Address.id == address_id, Address.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_user_addresses(db: AsyncSession, user_id: str):
    result = await db.execute(select(Address).where(Address.user_id == user_id))
    return result.scalars().all()


async def create_address(db: AsyncSession, user_id: str, data: dict) -> Address:
    if data.get("is_default"):
        await _unset_default(db, user_id)
    address = Address(user_id=user_id, **data)
    db.add(address)
    await db.flush()
    await db.refresh(address)
    return address


async def update_address(
    db: AsyncSession, address_id: str, user_id: str, data: dict
) -> Address | None:
    address = await get_address(db, address_id, user_id)
    if not address:
        return None
    if data.get("is_default"):
        await _unset_default(db, user_id)
    for k, v in data.items():
        setattr(address, k, v)
    await db.flush()
    await db.refresh(address)
    return address


async def delete_address(db: AsyncSession, address_id: str, user_id: str) -> bool:
    address = await get_address(db, address_id, user_id)
    if not address:
        return False
    await db.delete(address)
    await db.flush()
    return True


async def set_default_address(
    db: AsyncSession, address_id: str, user_id: str
) -> Address | None:
    address = await get_address(db, address_id, user_id)
    if not address:
        return None
    await _unset_default(db, user_id)
    address.is_default = True
    await db.flush()
    await db.refresh(address)
    return address


# ── helpers ──────────────────────────────────────────────────────────────────

async def _unset_default(db: AsyncSession, user_id: str) -> None:
    """Clear is_default on all addresses for a user."""
    result = await db.execute(
        select(Address).where(Address.user_id == user_id, Address.is_default == True)
    )
    for addr in result.scalars().all():
        addr.is_default = False