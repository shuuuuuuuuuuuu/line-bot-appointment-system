from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from typing import List, Optional
from datetime import datetime

# format
class ServiceSelection(BaseModel):
    name: str
    selected: bool

# request
class AppointmentCreate(BaseModel):
    line_user_id: str
    last_name: str
    first_name: str
    category: str
    service_items: List[str]
    user_message: Optional[str] = ""
    total_price: int
    total_duration: int
    service_dateTime: datetime

    @field_validator("user_message")
    @classmethod
    def strip_user_message(cls, value: Optional[str]) -> str:
        return (value or "").strip()

    @model_validator(mode="after")
    def require_message_for_akashic(self):
        if "阿卡西" in (self.category or "") and not self.user_message:
            raise ValueError("阿卡西預約須填寫問題簡述")
        return self

# response
class Appointment(BaseModel):
    id: int
    client_id: int
    service_dateTime: datetime
    expired: bool
    paid: bool
    total_price: int
    total_duration: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class Category(BaseModel):
    id: int
    category_name: str

    class Config:
        from_attributes = True

class Service(BaseModel):
    id: int
    service_name: str
    category_id: int
    price: int = 0
    duration_minutes: int = 60
    is_active: bool = True
    sort_order: int = 0

    class Config:
        from_attributes = True


class ServiceCreate(BaseModel):
    service_name: str = Field(min_length=1, max_length=255)
    category_id: int
    price: int = Field(ge=0)
    duration_minutes: int = Field(ge=1, le=480)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0)


class ServiceUpdate(BaseModel):
    service_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    category_id: Optional[int] = None
    price: Optional[int] = Field(default=None, ge=0)
    duration_minutes: Optional[int] = Field(default=None, ge=1, le=480)
    is_active: Optional[bool] = None
    sort_order: Optional[int] = Field(default=None, ge=0)


class ServiceAdminOut(BaseModel):
    id: int
    service_name: str
    category_id: int
    category_name: Optional[str] = None
    price: int
    duration_minutes: int
    is_active: bool
    sort_order: int

    class Config:
        from_attributes = True


class ServiceReorderItem(BaseModel):
    id: int
    sort_order: int = Field(ge=0)


class ServiceReorderRequest(BaseModel):
    items: List[ServiceReorderItem] = Field(min_length=1)


class MessageTemplateOut(BaseModel):
    id: int
    key: str
    name: str
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    body: str
    description: Optional[str] = None
    is_active: bool
    updated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MessageTemplateUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    body: Optional[str] = Field(default=None, min_length=1, max_length=4000)
    description: Optional[str] = Field(default=None, max_length=500)
    is_active: Optional[bool] = None
    category_id: Optional[int] = None


class BusinessHolidayOut(BaseModel):
    id: int
    holiday_date: str
    name: Optional[str] = None

    class Config:
        from_attributes = True


class BusinessHolidayCreate(BaseModel):
    holiday_date: str = Field(description="YYYY-MM-DD")
    name: Optional[str] = Field(default=None, max_length=100)


class BusinessSettingsOut(BaseModel):
    open_hour: int
    close_hour: int
    slot_interval_minutes: int
    buffer_minutes: int
    off_weekdays: List[int]
    max_advance_days: int
    slot_lock_minutes: int
    holidays: List[BusinessHolidayOut] = []


class BusinessSettingsUpdate(BaseModel):
    open_hour: Optional[int] = Field(default=None, ge=0, le=23)
    close_hour: Optional[int] = Field(default=None, ge=1, le=24)
    slot_interval_minutes: Optional[int] = Field(default=None, ge=15, le=240)
    buffer_minutes: Optional[int] = Field(default=None, ge=0, le=240)
    off_weekdays: Optional[List[int]] = None
    max_advance_days: Optional[int] = Field(default=None, ge=1, le=365)
    slot_lock_minutes: Optional[int] = Field(default=None, ge=1, le=120)


class AdminStatsCategoryOut(BaseModel):
    category_name: str
    appointment_count: int
    revenue: int


class AdminStatsServiceItemOut(BaseModel):
    service_name: str
    booking_count: int


class AdminStatsTrendPoint(BaseModel):
    label: str
    date: str
    confirmed_count: int
    revenue: int
    cancelled_count: int


class AdminStatsAppointmentOut(BaseModel):
    id: int
    client_name: str
    service_date_time: Optional[datetime] = None
    total_price: int = 0
    total_duration: Optional[int] = None
    status: str
    status_label: str
    category_name: Optional[str] = None
    service_names: List[str] = []
    user_message: Optional[str] = None
    payment_proof_received: bool = False
    payment_deadline_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class AdminStatsOut(BaseModel):
    period: str
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    confirmed_count: int
    revenue: int
    pending_payment_count: int
    awaiting_review_count: int
    cancelled_count: int
    upcoming_count: int
    by_category: List[AdminStatsCategoryOut] = []
    by_akashic_service: List[AdminStatsServiceItemOut] = []
    trend: List[AdminStatsTrendPoint] = []
    upcoming_appointments: List[AdminStatsAppointmentOut] = []
    recent_appointments: List[AdminStatsAppointmentOut] = []


class AdminLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class AdminToken(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminOut(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True