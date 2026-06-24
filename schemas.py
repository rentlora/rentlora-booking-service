from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8)
    confirm_password: str
    role: Literal["guest", "host"]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: EmailStr
    role: str
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: datetime


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    avatar_url: Optional[str] = None
    role: str
    created_at: datetime


class AuthResponse(BaseModel):
    user: UserOut
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    phone: Optional[str] = None
    avatar_url: Optional[str] = None


class PropertyMini(BaseModel):
    id: int
    title: str
    city: str
    location: Optional[str] = None
    price_per_night: Decimal
    first_image: Optional[str] = None


class GuestMini(BaseModel):
    id: int
    name: str
    email: EmailStr


class BookingCreateRequest(BaseModel):
    property_id: int
    check_in: date
    check_out: date
    guests_count: int


class BookingBase(BaseModel):
    id: int
    check_in: date
    check_out: date
    guests_count: int
    total_nights: int
    total_price: Decimal
    status: str
    created_at: datetime


class BookingListItem(BookingBase):
    property: PropertyMini


class BookingDetail(BookingBase):
    guest: GuestMini
    property: PropertyMini


class HostBookingItem(BaseModel):
    id: int
    check_in: date
    check_out: date
    guests_count: int
    total_price: Decimal
    status: str
    guest: GuestMini
    property: PropertyMini

class AdminStatsResponse(BaseModel):
    total_users: int
    total_properties: int
    total_bookings: int
    total_platform_revenue: Decimal

class UpdateRoleRequest(BaseModel):
    role: Literal["guest", "host", "admin"]
