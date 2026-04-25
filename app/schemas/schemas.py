from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, List, Literal

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1)
    phone: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    phone: Optional[str]
    role: str
    is_verified: bool
    avatar_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ProductOut(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str]
    price: float
    compare_price: Optional[float]
    sku: Optional[str]
    stock: int
    images: List[dict]
    attributes: dict
    is_active: bool
    is_featured: bool
    category_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float = Field(gt=0)
    compare_price: Optional[float] = None
    cost_price: Optional[float] = None
    sku: Optional[str] = None
    stock: int = Field(ge=0, default=0)
    weight: Optional[float] = None
    images: List[dict] = []
    attributes: dict = {}
    how_to: List[dict] = []
    is_active: bool = True
    is_featured: bool = False
    category_id: Optional[str] = None


class ProductUpdate(ProductCreate):
    name: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None


class CategoryOut(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str]
    image_url: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True

# ─── Category ────────────────────────────────────────────────────────────────

class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: Optional[str] = Field(default=None, max_length=500)
    image_url: Optional[str] = None
    is_active: bool = True

class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    slug: Optional[str] = Field(default=None, pattern=r"^[a-z0-9-]+$")
    description: Optional[str] = Field(default=None, max_length=500)
    image_url: Optional[str] = None
    is_active: Optional[bool] = None


class CartItem(BaseModel):
    product_id: str
    quantity: int = Field(ge=1)


class CartRequest(BaseModel):
    items: List[CartItem]


class CheckoutRequest(BaseModel):
    items: List[CartItem]
    address_id: str
    notes: Optional[str] = None


class OrderItemOut(BaseModel):
    id: str
    product_id: str
    product_name: str
    product_image: Optional[str]
    quantity: int
    unit_price: float
    total_price: float

    class Config:
        from_attributes = True


class OrderOut(BaseModel):
    id: str
    order_number: str
    status: str
    payment_status: str
    subtotal: float
    shipping_fee: float
    discount: float
    total: float
    shipping_address: dict
    payment_url: Optional[str] = None
    qr_code: Optional[str] = None
    tracking_number: Optional[str] = None
    notes: Optional[str] = None
    items: List[OrderItemOut]
    created_at: datetime

    class Config:
        from_attributes = True


class AddressCreate(BaseModel):
    full_name: str
    phone: str
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    province: str
    postal_code: str
    country: str = "Thailand"
    is_default: bool = False


class AddressOut(AddressCreate):
    id: str

    class Config:
        from_attributes = True


class PaginatedProducts(BaseModel):
    items: List[ProductOut]
    total: int
    page: int
    per_page: int
    total_pages: int


# ── Reviews ───────────────────────────────────────────────────────────────────
class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    title: Optional[str] = None
    body: Optional[str] = None


class ReviewOut(BaseModel):
    id: str
    product_id: str
    user_id: str
    reviewer_name: str       
    rating: int
    title: Optional[str]
    body: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ProductDetailOut(ProductOut):
    """Extended product info for the product detail page."""
    weight: Optional[float] = None
    how_to: List[dict] = []
    avg_rating: float = 0.0
    review_count: int = 0
    sold_count: int = 0
    reviews: List[ReviewOut] = []

# ─── Coupon ──────────────────────────────────────────────────────────────────

class CouponCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    discount_type: Literal["percent", "fixed"]
    discount_value: float = Field(gt=0)
    min_purchase: Optional[float] = Field(default=None, ge=0)
    max_uses: Optional[int] = Field(default=None, ge=1)
    expires_at: Optional[datetime] = None
    is_active: bool = True
    description: Optional[str] = Field(default=None, max_length=200)


class CouponUpdate(BaseModel):
    code: Optional[str] = Field(default=None, min_length=1, max_length=50)
    discount_type: Optional[Literal["percent", "fixed"]] = None
    discount_value: Optional[float] = Field(default=None, gt=0)
    min_purchase: Optional[float] = Field(default=None, ge=0)
    max_uses: Optional[int] = Field(default=None, ge=1)
    expires_at: Optional[datetime] = None
    is_active: Optional[bool] = None
    description: Optional[str] = Field(default=None, max_length=200)

# ─── Customer ────────────────────────────────────────────────────────────────

class CustomerUpdate(BaseModel):
    is_active: Optional[bool] = None
    


# ─── Settings ────────────────────────────────────────────────────────────────

class ShopSettingsUpdate(BaseModel):
    type: Literal["general", "shipping"]
    data: dict 

class AddressUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    is_default: Optional[bool] = None
 
 
# ─── Password ────────────────────────────────────────────────────────────────
 
class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)