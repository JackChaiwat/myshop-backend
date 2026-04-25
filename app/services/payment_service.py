"""
payment_service.py — Lemon Squeezy (optional payment provider)
Primary payment is Omise (see omise_service.py)
"""
import httpx
import hmac
import hashlib
from app.core.config import settings


async def create_checkout_session(order, user) -> str:
    """Create a Lemon Squeezy checkout and return payment URL"""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.lemonsqueezy.com/v1/checkouts",
            headers={
                "Authorization": f"Bearer {settings.LEMONSQUEEZY_API_KEY}",
                "Accept": "application/vnd.api+json",
                "Content-Type": "application/vnd.api+json",
            },
            json={
                "data": {
                    "type": "checkouts",
                    "attributes": {
                        "checkout_data": {
                            "email": user.email,
                            "name": user.full_name,
                            "custom": {"order_id": order.id},
                        },
                        "checkout_options": {"embed": False},
                        "product_options": {
                            "name": f"Order {order.order_number}",
                            "description": f"{len(order.items)} items — Total: {order.total:.2f} THB",
                            "redirect_url": f"https://yourdomain.com/orders/{order.id}",
                        },
                        "preview": False,
                    },
                    "relationships": {
                        "store": {"data": {"type": "stores", "id": settings.LEMONSQUEEZY_STORE_ID}},
                        "variant": {"data": {"type": "variants", "id": "YOUR_VARIANT_ID"}},
                    },
                }
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["data"]["attributes"]["url"]


def verify_lemon_webhook(body: bytes, signature: str) -> bool:
    """Verify LemonSqueezy webhook signature using HMAC-SHA256."""
    # hmac.new(key, msg, digestmod) — correct Python stdlib API
    expected = hmac.new(
        settings.LEMONSQUEEZY_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
