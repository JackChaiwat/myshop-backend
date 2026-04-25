import httpx
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


async def trigger_new_order_workflow(order_data: dict):
    if not settings.N8N_WEBHOOK_URL:
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                settings.N8N_WEBHOOK_URL + "/new-order",
                json=order_data,
                timeout=5,
            )
    except Exception as e:
        logger.warning(f"n8n webhook failed: {e}")
