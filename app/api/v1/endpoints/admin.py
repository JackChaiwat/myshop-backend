from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta
from typing import Optional
import json
from app.schemas.schemas import (
    CategoryCreate, CategoryUpdate,
    CouponCreate, CouponUpdate,
    CustomerUpdate, ShopSettingsUpdate,
)
from app.db.session import get_db
from app.core.auth import require_admin
from app.models.models import Order, User, Product, Category, OrderStatus

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0)
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)

    total_orders = (await db.execute(select(func.count()).select_from(Order))).scalar_one()
    total_revenue = (await db.execute(select(func.sum(Order.total)).where(Order.payment_status == "paid"))).scalar_one() or 0
    total_customers = (await db.execute(select(func.count()).select_from(User).where(User.role == "customer"))).scalar_one()
    total_products = (await db.execute(select(func.count()).select_from(Product).where(Product.is_active == True))).scalar_one()

    # This month
    month_revenue = (await db.execute(select(func.sum(Order.total)).where(and_(Order.payment_status == "paid", Order.created_at >= month_start)))).scalar_one() or 0
    month_orders = (await db.execute(select(func.count()).select_from(Order).where(Order.created_at >= month_start))).scalar_one()
    month_customers = (await db.execute(select(func.count()).select_from(User).where(and_(User.role == "customer", User.created_at >= month_start)))).scalar_one()

    # Prev month
    prev_revenue = (await db.execute(select(func.sum(Order.total)).where(and_(Order.payment_status == "paid", Order.created_at >= prev_month_start, Order.created_at < month_start)))).scalar_one() or 1
    prev_orders = (await db.execute(select(func.count()).select_from(Order).where(and_(Order.created_at >= prev_month_start, Order.created_at < month_start)))).scalar_one() or 1
    prev_customers = (await db.execute(select(func.count()).select_from(User).where(and_(User.role == "customer", User.created_at >= prev_month_start, User.created_at < month_start)))).scalar_one() or 1

    # Status counts
    pending = (await db.execute(select(func.count()).select_from(Order).where(Order.status == "pending"))).scalar_one()
    paid = (await db.execute(select(func.count()).select_from(Order).where(Order.status == "paid"))).scalar_one()
    shipped = (await db.execute(select(func.count()).select_from(Order).where(Order.status == "shipped"))).scalar_one()
    cancelled = (await db.execute(select(func.count()).select_from(Order).where(Order.status == "cancelled"))).scalar_one()

    # Recent orders with customer name
    recent_q = await db.execute(
        select(Order, User.full_name.label('customer_name'))
        .join(User, Order.user_id == User.id)
        .order_by(Order.created_at.desc()).limit(10)
    )
    recent_orders = [
        {
            "id": o.id, "order_number": o.order_number, "total": o.total,
            "status": o.status, "created_at": o.created_at.isoformat(),
            "customer_name": name,
        }
        for o, name in recent_q.all()
    ]

    # Top products
    from app.models.models import OrderItem
    top_q = await db.execute(
        select(Product.id, Product.name, Product.images, func.sum(OrderItem.quantity).label('sold'), func.sum(OrderItem.total_price).label('revenue'))
        .join(OrderItem, Product.id == OrderItem.product_id)
        .group_by(Product.id, Product.name, Product.images)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(5)
    )
    top_products = [
        {"id": id, "name": name, "image": images[0]["url"] if images else None, "sold": int(sold or 0), "revenue": float(revenue or 0)}
        for id, name, images, sold, revenue in top_q.all()
    ]

    return {
        "total_orders": total_orders,
        "total_revenue": float(total_revenue),
        "total_customers": total_customers,
        "total_products": total_products,
        "revenue_change": round((month_revenue - prev_revenue) / prev_revenue * 100) if prev_revenue else 0,
        "orders_change": round((month_orders - prev_orders) / prev_orders * 100) if prev_orders else 0,
        "customers_change": round((month_customers - prev_customers) / prev_customers * 100) if prev_customers else 0,
        "pending_orders": pending,
        "paid_orders": paid,
        "shipped_orders": shipped,
        "cancelled_orders": cancelled,
        "recent_orders": recent_orders,
        "top_products": top_products,
    }


@router.get("/sales-chart")
async def get_sales_chart(db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    days = 30
    daily = []
    for i in range(days - 1, -1, -1):
        day = datetime.utcnow() - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        revenue = (await db.execute(select(func.sum(Order.total)).where(and_(Order.payment_status == "paid", Order.created_at >= day_start, Order.created_at < day_end)))).scalar_one() or 0
        orders = (await db.execute(select(func.count()).select_from(Order).where(and_(Order.created_at >= day_start, Order.created_at < day_end)))).scalar_one()
        daily.append({"date": day.strftime("%d/%m"), "revenue": float(revenue), "orders": orders})
    return {"daily": daily}


@router.get("/orders")
async def list_all_orders(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    q = select(Order, User.full_name.label('customer_name')).join(User, Order.user_id == User.id)
    if status:
        q = q.where(Order.status == status)
    if search:
        q = q.where(Order.order_number.ilike(f"%{search}%"))
    q = q.order_by(Order.created_at.desc())

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()

    orders_q = await db.execute(
        select(Order, User.full_name)
        .join(User, Order.user_id == User.id)
        .where(Order.id.in_(
            select(Order.id).join(User, Order.user_id == User.id)
            .where(*(
                ([Order.status == status] if status else []) +
                ([Order.order_number.ilike(f"%{search}%")] if search else [])
            ))
            .order_by(Order.created_at.desc())
            .offset((page - 1) * per_page).limit(per_page)
        ))
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
    )

    items = []
    for o, cname in orders_q.all():
        items.append({
            "id": o.id, "order_number": o.order_number, "status": o.status,
            "payment_status": o.payment_status, "total": o.total,
            "subtotal": o.subtotal, "shipping_fee": o.shipping_fee,
            "shipping_address": o.shipping_address, "tracking_number": o.tracking_number,
            "payment_provider": o.payment_provider, "payment_id": o.payment_id,
            "created_at": o.created_at.isoformat(), "customer_name": cname,
            "items": [{"id": i.id, "product_name": i.product_name, "quantity": i.quantity, "total_price": i.total_price} for i in o.items],
        })

    return {"items": items, "total": total, "page": page, "per_page": per_page, "total_pages": max(1, (total + per_page - 1) // per_page)}


@router.delete("/orders/{order_id}")
async def delete_order(order_id: str, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    from app.models.models import OrderItem, ChatMessage
    result = await db.execute(select(Order).where(Order.id == order_id).options(selectinload(Order.items)))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # ลบ chat_messages ก่อน (FK → orders)
    chat_result = await db.execute(select(ChatMessage).where(ChatMessage.order_id == order_id))
    for msg in chat_result.scalars().all():
        await db.delete(msg)

    # ลบ order_items ก่อน (FK → orders)
    for item in order.items:
        await db.delete(item)

    await db.delete(order)
    await db.commit()
    return {"message": "Deleted"}


@router.get("/customers")
async def list_customers(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    from app.models.models import OrderItem
    q = select(User).where(User.role == "customer")
    if search:
        q = q.where((User.full_name.ilike(f"%{search}%")) | (User.email.ilike(f"%{search}%")))
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    users_q = await db.execute(q.offset((page-1)*per_page).limit(per_page).order_by(User.created_at.desc()))
    users = users_q.scalars().all()
    items = []
    for u in users:
        order_count = (await db.execute(select(func.count()).select_from(Order).where(Order.user_id == u.id))).scalar_one()
        total_spent = (await db.execute(select(func.sum(Order.total)).where(and_(Order.user_id == u.id, Order.payment_status == "paid")))).scalar_one() or 0
        items.append({"id": u.id, "full_name": u.full_name, "email": u.email, "phone": u.phone, "is_active": u.is_active, "created_at": u.created_at.isoformat(), "order_count": order_count, "total_spent": float(total_spent)})
    return {"items": items, "total": total, "page": page, "per_page": per_page, "total_pages": max(1, (total + per_page - 1) // per_page)}


@router.put("/customers/{user_id}")
async def update_customer(user_id: str, body: CustomerUpdate, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    return {"message": "Updated"}


@router.get("/categories")
async def list_categories(db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    result = await db.execute(select(Category).order_by(Category.name))
    cats = result.scalars().all()
    items = []
    for c in cats:
        count = (await db.execute(select(func.count()).select_from(Product).where(Product.category_id == c.id))).scalar_one()
        items.append({"id": c.id, "name": c.name, "slug": c.slug, "description": c.description, "image_url": c.image_url, "is_active": c.is_active, "product_count": count})
    return items


@router.post("/categories")
async def create_category(body: CategoryCreate, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    cat = Category(
        name=body.name,
        slug=body.slug,
        description=body.description,
        image_url=body.image_url,
        is_active=body.is_active,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


@router.put("/categories/{cat_id}")
async def update_category(cat_id: str, body: CategoryUpdate, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    result = await db.execute(select(Category).where(Category.id == cat_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(cat, field, value)
    await db.commit()
    return {"message": "Updated"}


@router.delete("/categories/{cat_id}")
async def delete_category(cat_id: str, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    result = await db.execute(select(Category).where(Category.id == cat_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Not found")
    await db.delete(cat)
    await db.commit()
    return {"message": "Deleted"}


@router.get("/reports")
async def get_reports(
    mode: str = Query("daily"),          # daily | monthly | yearly
    # daily params
    from_: Optional[str] = Query(None, alias="from"),   # YYYY-MM-DD
    to: Optional[str]    = Query(None),                  # YYYY-MM-DD
    # monthly params
    from_month: Optional[int] = Query(None),
    from_year:  Optional[int] = Query(None),
    to_month:   Optional[int] = Query(None),
    to_year:    Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    import calendar
    from app.models.models import OrderItem

    THAI_MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
                   "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]

    now = datetime.utcnow()

    # ── คำนวณ start / end ตาม mode ────────────────────────────────────────────
    if mode == "yearly":
        fy = from_year or (now.year - 2)
        ty = to_year   or now.year
        start = datetime(fy, 1, 1)
        end   = datetime(ty + 1, 1, 1)

    elif mode == "monthly":
        fm = from_month or 1;  fy = from_year or now.year
        tm = to_month   or now.month; ty = to_year or now.year
        start = datetime(fy, fm, 1)
        _, last = calendar.monthrange(ty, tm)
        end = datetime(ty, tm, last, 23, 59, 59) + timedelta(seconds=1)

    else:  # daily
        from_str = from_ or (now - timedelta(days=29)).strftime("%Y-%m-%d")
        to_str   = to    or now.strftime("%Y-%m-%d")
        start = datetime.strptime(from_str, "%Y-%m-%d")
        end   = datetime.strptime(to_str,   "%Y-%m-%d").replace(hour=23, minute=59, second=59) + timedelta(seconds=1)

    # ── Summary stats ──────────────────────────────────────────────────────────
    total_revenue = (await db.execute(
        select(func.sum(Order.total)).where(and_(Order.payment_status == "paid", Order.created_at >= start, Order.created_at < end))
    )).scalar_one() or 0
    total_orders = (await db.execute(
        select(func.count()).select_from(Order).where(and_(Order.created_at >= start, Order.created_at < end))
    )).scalar_one()
    new_customers = (await db.execute(
        select(func.count()).select_from(User).where(and_(User.role == "customer", User.created_at >= start, User.created_at < end))
    )).scalar_one()
    avg_order = float(total_revenue) / total_orders if total_orders else 0

    # ── Chart data ─────────────────────────────────────────────────────────────
    chart = []

    if mode == "yearly":
        for y in range(fy, ty + 1):
            yr_start = datetime(y, 1, 1)
            yr_end   = datetime(y + 1, 1, 1)
            rev  = (await db.execute(select(func.sum(Order.total)).where(and_(Order.payment_status == "paid", Order.created_at >= yr_start, Order.created_at < yr_end)))).scalar_one() or 0
            ords = (await db.execute(select(func.count()).select_from(Order).where(and_(Order.created_at >= yr_start, Order.created_at < yr_end)))).scalar_one()
            chart.append({"date": str(y), "revenue": float(rev), "orders": ords})

    elif mode == "monthly":
        # วน loop จาก from → to
        cur_y, cur_m = fy, fm
        while (cur_y, cur_m) <= (ty, tm):
            _, last_day = calendar.monthrange(cur_y, cur_m)
            mo_start = datetime(cur_y, cur_m, 1)
            mo_end   = datetime(cur_y, cur_m, last_day, 23, 59, 59) + timedelta(seconds=1)
            rev  = (await db.execute(select(func.sum(Order.total)).where(and_(Order.payment_status == "paid", Order.created_at >= mo_start, Order.created_at < mo_end)))).scalar_one() or 0
            ords = (await db.execute(select(func.count()).select_from(Order).where(and_(Order.created_at >= mo_start, Order.created_at < mo_end)))).scalar_one()
            chart.append({"date": f"{THAI_MONTHS[cur_m - 1]} {cur_y}", "revenue": float(rev), "orders": ords})
            cur_m += 1
            if cur_m > 12:
                cur_m = 1; cur_y += 1

    else:  # daily
        cur = start
        while cur < end:
            day_start = cur
            day_end   = cur + timedelta(days=1)
            rev  = (await db.execute(select(func.sum(Order.total)).where(and_(Order.payment_status == "paid", Order.created_at >= day_start, Order.created_at < day_end)))).scalar_one() or 0
            ords = (await db.execute(select(func.count()).select_from(Order).where(and_(Order.created_at >= day_start, Order.created_at < day_end)))).scalar_one()
            chart.append({"date": cur.strftime("%d/%m"), "revenue": float(rev), "orders": ords})
            cur = day_end

    # ── Top products ───────────────────────────────────────────────────────────
    top_q = await db.execute(
        select(Product.name, func.sum(OrderItem.quantity).label('sold'))
        .join(OrderItem, Product.id == OrderItem.product_id)
        .join(Order, OrderItem.order_id == Order.id)
        .where(and_(Order.created_at >= start, Order.created_at < end))
        .group_by(Product.name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(10)
    )
    top_products = [{"name": name[:15], "sold": int(sold or 0)} for name, sold in top_q.all()]

    # ── By category ────────────────────────────────────────────────────────────
    by_cat_q = await db.execute(
        select(Category.name, func.sum(Order.total).label('revenue'))
        .join(Product, Category.id == Product.category_id)
        .join(OrderItem, Product.id == OrderItem.product_id)
        .join(Order, OrderItem.order_id == Order.id)
        .where(and_(Order.payment_status == "paid", Order.created_at >= start, Order.created_at < end))
        .group_by(Category.name)
        .order_by(func.sum(Order.total).desc())
    )
    by_category = [{"name": n, "revenue": float(r or 0)} for n, r in by_cat_q.all()]

    return {
        "total_revenue": float(total_revenue),
        "total_orders": total_orders,
        "new_customers": new_customers,
        "avg_order_value": round(avg_order, 2),
        "chart": chart,
        "top_products": top_products,
        "by_category": by_category,
    }


@router.get("/coupons")
async def list_coupons(db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    from app.models.models import Coupon
    result = await db.execute(select(Coupon).order_by(Coupon.created_at.desc()))
    return result.scalars().all()


@router.post("/coupons")
async def create_coupon(body: CouponCreate, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    from app.models.models import Coupon
    coupon = Coupon(**body.model_dump())
    db.add(coupon)
    await db.commit()
    await db.refresh(coupon)
    return coupon



@router.put("/coupons/{coupon_id}")
async def update_coupon(coupon_id: str, body: CouponUpdate, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    from app.models.models import Coupon
    result = await db.execute(select(Coupon).where(Coupon.id == coupon_id))
    coupon = result.scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail="Not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(coupon, field, value)
    await db.commit()
    return {"message": "Updated"}


@router.delete("/coupons/{coupon_id}")
async def delete_coupon(coupon_id: str, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    from app.models.models import Coupon
    result = await db.execute(select(Coupon).where(Coupon.id == coupon_id))
    coupon = result.scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail="Not found")
    await db.delete(coupon)
    await db.commit()
    return {"message": "Deleted"}


@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    from app.models.models import ShopSetting
    result = await db.execute(select(ShopSetting))
    settings = result.scalars().all()
    data: dict = {"general": {}, "shipping": {}}
    for s in settings:
        try:
            data[s.category][s.key] = json.loads(s.value)
        except Exception:
            data.setdefault(s.category, {})[s.key] = s.value
    return data


@router.put("/settings")
async def update_settings(body: dict, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    from app.models.models import ShopSetting
    category = body.get("type", "general")
    settings_data = body.get("data", {})
    for key, value in settings_data.items():
        result = await db.execute(select(ShopSetting).where(and_(ShopSetting.category == category, ShopSetting.key == key)))
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = json.dumps(value)
        else:
            db.add(ShopSetting(category=category, key=key, value=json.dumps(value)))
    await db.commit()
    return {"message": "Saved"}