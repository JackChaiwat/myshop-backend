import httpx
import base64
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


async def create_promptpay_charge(order) -> dict:
    auth = base64.b64encode(f"{settings.OMISE_SECRET_KEY}:".encode()).decode()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.omise.co/charges",
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/json",
            },
            json={
                "amount": int(order.total * 100),
                "currency": "thb",
                "source": {"type": "promptpay"},
                "description": f"Order {order.order_number}",
                "metadata": {
                    "order_id": order.id,
                    "order_number": order.order_number,
                },
            },
        )
        resp.raise_for_status()
        data = resp.json()

        download_uri = (
            data.get("source", {})
            .get("scannable_code", {})
            .get("image", {})
            .get("download_uri", "")
        )

        qr_svg = ""
        if download_uri:
            try:
                img_resp = await client.get(
                    download_uri,
                    headers={"Authorization": f"Basic {auth}"},
                    follow_redirects=True,
                )
                content_type = img_resp.headers.get("content-type", "")
                if "svg" in content_type or img_resp.content.startswith(b"<svg"):
                    qr_svg = img_resp.content.decode("utf-8")
                else:
                    # redirect HTML — try to follow manually
                    qr_svg = ""
            except Exception as e:
                logger.warning(f"QR fetch failed: {e}")

        return {
            "charge_id": data["id"],
            "amount": data["amount"],
            "qr_code_url": qr_svg,
            "authorize_uri": data.get("authorize_uri", ""),
            "status": data["status"],
        }


async def get_charge_status(charge_id: str) -> str:
    auth = base64.b64encode(f"{settings.OMISE_SECRET_KEY}:".encode()).decode()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.omise.co/charges/{charge_id}",
            headers={"Authorization": f"Basic {auth}"},
        )
        resp.raise_for_status()
        return resp.json()["status"]
