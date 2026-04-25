from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from typing import List, Optional
import hmac, hashlib, uuid, logging

from app.db.session import get_db
from app.core.auth import get_current_user, require_admin
from app.core.config import settings
from app.schemas.schemas import CheckoutRequest, OrderOut, OrderItemOut
from app.models.models import Order, Product
from app.db.crud.order import create_order, get_order, get_user_orders, update_order_status
from app.db.crud.product import get_product_by_id, update_stock
from app.db.crud.address import get_address
from app.services.omise_service import create_promptpay_charge, get_charge_status
from app.services.email_service import send_order_status_update
from app.services.n8n_service import trigger_new_order_workflow

router = APIRouter(prefix="/orders", tags=["orders"])
logger = logging.getLogger(__name__)


# FIX: UUID-based order number — no collision risk
def gen_order_number() -> str:
    return "ORD-" + uuid.uuid4().hex[:8].upper()


# FIX: Omise webhook HMAC-SHA256 signature verification
def _verify_omise_signature(body: bytes, signature: str) -> bool:
    if not settings.OMISE_WEBHOOK_SECRET:
        logger.error(
            "OMISE_WEBHOOK_SECRET is not configured — rejecting all webhook calls. "
            "Set this variable before deploying."
        )
        return False  # ✅ ปลอดภัย: reject แทนที่จะ allow
    expected = hmac.new(
        settings.OMISE_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def to_order_out(order: Order, qr_code: str = None) -> OrderOut:
    return OrderOut(
        id=order.id,
        order_number=order.order_number,
        status=order.status,
        payment_status=order.payment_status,
        subtotal=order.subtotal,
        shipping_fee=order.shipping_fee,
        discount=order.discount,
        total=order.total,
        shipping_address=order.shipping_address,
        payment_url=order.payment_url,
        qr_code=qr_code,
        tracking_number=order.tracking_number,
        notes=order.notes,
        created_at=order.created_at,
        items=[OrderItemOut(
            id=item.id,
            product_id=item.product_id,
            product_name=item.product_name,
            product_image=item.product_image,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total_price=item.total_price,
        ) for item in order.items],
    )


@router.post("/checkout", response_model=OrderOut)
async def checkout(
    body: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    address = await get_address(db, body.address_id, current_user.id)
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")

    # FIX: Lock rows with SELECT FOR UPDATE — prevents race condition on stock
    product_ids = [item.product_id for item in body.items]
    locked_result = await db.execute(
        select(Product)
        .where(Product.id.in_(product_ids))
        .with_for_update()
    )
    locked_products = {p.id: p for p in locked_result.scalars().all()}

    items = []
    subtotal = 0.0
    for cart_item in body.items:
        product = locked_products.get(cart_item.product_id)
        if not product or not product.is_active:
            raise HTTPException(status_code=400, detail=f"Product {cart_item.product_id} not available")
        if product.stock < cart_item.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for {product.name}")

        # FIX: Deduct stock immediately at checkout (not waiting for Omise webhook)
        product.stock -= cart_item.quantity

        item_total = product.price * cart_item.quantity
        subtotal += item_total
        items.append({
            "product_id": product.id,
            "product_name": product.name,
            "product_image": product.images[0]["url"] if product.images else None,
            "quantity": cart_item.quantity,
            "unit_price": product.price,
            "total_price": item_total,
        })

    shipping_fee = 0.0 if subtotal >= 1000 else 50.0
    total = subtotal + shipping_fee

    address_snapshot = {
        "full_name": address.full_name,
        "phone": address.phone,
        "address_line1": address.address_line1,
        "address_line2": address.address_line2,
        "city": address.city,
        "province": address.province,
        "postal_code": address.postal_code,
        "country": address.country,
    }

    order = await create_order(db, {
        "order_number": gen_order_number(),
        "user_id": current_user.id,
        "subtotal": subtotal,
        "shipping_fee": shipping_fee,
        "discount": 0,
        "total": total,
        "shipping_address": address_snapshot,
        "notes": body.notes,
        "items": items,
    })

    qr_code = None
    try:
        charge = await create_promptpay_charge(order)
        qr_code = charge["qr_code_url"]
        order.payment_provider = "omise"
        order.payment_id = charge["charge_id"]
        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
        order.payment_url = f"{frontend_url}/orders/{order.id}/success"
    except Exception as e:
        logger.error(f"Omise charge failed: {e}")
        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
        order.payment_url = f"{frontend_url}/orders/{order.id}/success"

    await db.commit()

    await trigger_new_order_workflow({
        "id": order.id,
        "order_number": order.order_number,
        "total": order.total,
    })

    return to_order_out(order, qr_code=qr_code)


@router.get("/check-payment/{order_id}")
async def check_payment(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    order = await get_order(db, order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    if not order.payment_id:
        return {"status": "pending"}
    try:
        status = await get_charge_status(order.payment_id)
        if status == "successful" and order.payment_status != "paid":
            await update_order_status(db, order_id, status="paid", payment_status="paid")
            await db.commit()
        return {"status": status}
    except Exception:
        return {"status": "unknown"}


@router.post("/{order_id}/request-payment")
async def request_payment(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    order = await get_order(db, order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.payment_status == "paid":
        raise HTTPException(status_code=400, detail="Order already paid")
    try:
        charge = await create_promptpay_charge(order)
        order.payment_id = charge["charge_id"]
        order.payment_provider = "omise"
        await db.commit()
        return {"qr_code": charge["qr_code_url"]}
    except Exception as e:
        logger.error(f"request_payment failed: {e}")
        raise HTTPException(status_code=500, detail="Cannot create payment")



@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    order = await get_order(db, order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != "pending":
        raise HTTPException(status_code=400, detail="ยกเลิกได้เฉพาะคำสั่งซื้อที่ยังไม่ได้ชำระเงิน")
    if order.payment_status == "paid":
        raise HTTPException(status_code=400, detail="คำสั่งซื้อที่ชำระเงินแล้วไม่สามารถยกเลิกได้")

    # คืน stock
    for item in order.items:
        result = await db.execute(select(Product).where(Product.id == item.product_id).with_for_update())
        product = result.scalar_one_or_none()
        if product:
            product.stock += item.quantity

    order.status = "cancelled"
    order.notes = (order.notes or "") + f"\n[ยกเลิกโดยลูกค้า] {body.get('reason', '')}"
    await db.commit()
    return {"message": "ยกเลิกคำสั่งซื้อแล้ว"}


@router.get("", response_model=List[OrderOut])
async def my_orders(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    orders = await get_user_orders(db, current_user.id)
    return [to_order_out(o) for o in orders]


@router.get("/{order_id}", response_model=OrderOut)
async def get_order_detail(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    order = await get_order(db, order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    return to_order_out(order)


# FIX: Webhook now verifies Omise-Signature header before processing
@router.post("/webhook/omise")
async def omise_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    omise_signature: Optional[str] = Header(None, alias="Omise-Signature"),
):
    raw_body = await request.body()

    if not omise_signature or not _verify_omise_signature(raw_body, omise_signature):
        logger.warning("Omise webhook: invalid or missing signature — rejected")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        import json
        payload = json.loads(raw_body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event = payload.get("key")
    charge = payload.get("data", {})

    if event == "charge.complete":
        order_id = charge.get("metadata", {}).get("order_id")
        status = charge.get("status")
        if order_id and status == "successful":
            order = await get_order(db, order_id)
            # Guard: only update if not already paid (idempotent)
            if order and order.payment_status != "paid":
                await update_order_status(db, order_id, status="paid", payment_status="paid")
                # Stock already deducted at checkout — do NOT deduct again here
                await db.commit()

    return {"status": "ok"}


@router.put("/{order_id}/status")
async def admin_update_status(
    order_id: str,
    status: str,
    tracking_number: str = None,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    order = await update_order_status(db, order_id, status=status, tracking_number=tracking_number)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    await db.commit()
    await send_order_status_update(order)
    return to_order_out(order)