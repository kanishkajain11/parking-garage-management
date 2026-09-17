from pydantic import BaseModel, EmailStr
from typing import Optional


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    name: str


class CheckInRequest(BaseModel):
    vehicle_plate: str
    vehicle_type: str = "STANDARD"
    spot_id: Optional[int] = None


class PricingUpdateRequest(BaseModel):
    first_hour_rate: float
    additional_hour_rate: float
    daily_cap: float
    spot_type: Optional[str] = None


class RateCardImportRequest(BaseModel):
    raw_text: str


class TransferRequest(BaseModel):
    old_plate: str
    new_plate: str


class ClockRequest(BaseModel):
    now: Optional[str] = None
