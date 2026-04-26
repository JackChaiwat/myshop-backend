from fastapi import APIRouter
from app.api.v1.endpoints import auth, products, orders, users, admin, chat, wishlist, verification, seed

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(products.router)
api_router.include_router(orders.router)
api_router.include_router(users.router)
api_router.include_router(admin.router)
api_router.include_router(chat.router)
api_router.include_router(wishlist.router)
api_router.include_router(verification.router)
api_router.include_router(seed.router)