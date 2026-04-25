import meilisearch
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    client = meilisearch.Client(settings.MEILISEARCH_URL, settings.MEILISEARCH_API_KEY)
    index = client.index("products")
except Exception as e:
    logger.warning(f"Meilisearch init failed: {e}")
    client = None
    index = None


def setup_search_index():
    if not index:
        return
    try:
        index.update_searchable_attributes(["name", "description", "sku"])
        index.update_filterable_attributes(["category_id", "price", "is_active", "is_featured"])
        index.update_sortable_attributes(["price", "created_at"])
    except Exception as e:
        logger.warning(f"Meilisearch setup failed: {e}")


async def index_product(product):
    if not index:
        return
    try:
        index.add_documents([{
            "id": product.id,
            "name": product.name,
            "slug": product.slug,
            "description": product.description,
            "price": product.price,
            "images": product.images,
            "category_id": product.category_id,
            "is_active": product.is_active,
            "is_featured": product.is_featured,
            "stock": product.stock,
        }])
    except Exception as e:
        logger.warning(f"Meilisearch index_product failed: {e}")


async def delete_product_index(product_id: str):
    if not index:
        return
    try:
        index.delete_document(product_id)
    except Exception as e:
        logger.warning(f"Meilisearch delete failed: {e}")


async def search_products(query: str, filters: dict = None, page: int = 1, per_page: int = 20):
    if not index:
        return {"hits": [], "estimatedTotalHits": 0}
    try:
        filter_str = "is_active = true"
        if filters:
            if filters.get("category_id"):
                filter_str += f" AND category_id = '{filters['category_id']}'"
            if filters.get("min_price"):
                filter_str += f" AND price >= {filters['min_price']}"
            if filters.get("max_price"):
                filter_str += f" AND price <= {filters['max_price']}"
        return index.search(query, {
            "filter": filter_str,
            "limit": per_page,
            "offset": (page - 1) * per_page,
        })
    except Exception as e:
        logger.warning(f"Meilisearch search failed: {e}")
        return {"hits": [], "estimatedTotalHits": 0}
