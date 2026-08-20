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
    coupon_code: Optional[str] = None

    @field_validator("user_message")
    @classmethod
    def strip_user_message(cls, value: Optional[str]) -> str:
        return (value or "").strip()

    @field_validator("coupon_code")
    @classmethod
    def strip_coupon_code(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

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


class BusinessTimeSlot(BaseModel):
    open_hour: int = Field(ge=0, le=23)
    close_hour: int = Field(ge=1, le=24)

    @model_validator(mode="after")
    def validate_range(self):
        if self.open_hour >= self.close_hour:
            raise ValueError("開始營業時間須早於結束時間")
        return self


class BusinessWeeklyHoursOut(BaseModel):
    weekday: int = Field(ge=0, le=6)
    is_open: bool
    open_hour: int
    close_hour: int
    time_slots: List[BusinessTimeSlot] = []


class BusinessWeeklyHoursItem(BaseModel):
    weekday: int = Field(ge=0, le=6)
    is_open: bool
    open_hour: int = Field(ge=0, le=23)
    close_hour: int = Field(ge=1, le=24)
    time_slots: List[BusinessTimeSlot] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_hours(self):
        if self.is_open:
            if self.time_slots:
                return self
            if self.open_hour >= self.close_hour:
                raise ValueError("開始營業時間須早於結束時間")
        return self


class BusinessWeeklyHoursUpdate(BaseModel):
    items: List[BusinessWeeklyHoursItem] = Field(min_length=7, max_length=7)


class BusinessDateOverrideOut(BaseModel):
    id: int
    target_date: str
    is_open: bool
    open_hour: Optional[int] = None
    close_hour: Optional[int] = None
    time_slots: List[BusinessTimeSlot] = []
    note: Optional[str] = None


class BusinessDateOverrideCreate(BaseModel):
    target_date: str = Field(description="YYYY-MM-DD")
    is_open: bool
    open_hour: Optional[int] = Field(default=None, ge=0, le=23)
    close_hour: Optional[int] = Field(default=None, ge=1, le=24)
    time_slots: List[BusinessTimeSlot] = Field(default_factory=list)
    note: Optional[str] = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_hours(self):
        if self.is_open:
            if self.time_slots:
                return self
            if self.open_hour is None or self.close_hour is None:
                raise ValueError("特別營業日須設定開始與結束時間")
            if self.open_hour >= self.close_hour:
                raise ValueError("開始營業時間須早於結束時間")
        return self


class BusinessSettingsOut(BaseModel):
    open_hour: int
    close_hour: int
    slot_interval_minutes: int
    buffer_minutes: int
    off_weekdays: List[int]
    max_advance_days: int
    slot_lock_minutes: int
    holidays: List[BusinessHolidayOut] = []
    weekly_hours: List[BusinessWeeklyHoursOut] = []
    date_overrides: List[BusinessDateOverrideOut] = []


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


class AppointmentExportRequest(BaseModel):
    period: str = Field(default="month", pattern="^(week|month|all)$")
    appointment_ids: Optional[List[int]] = None


class CouponCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=3, max_length=100)
    category_id: int
    valid_from: str = Field(description="YYYY-MM-DD")
    valid_to: str = Field(description="YYYY-MM-DD")
    is_active: bool = True
    max_uses: int = Field(default=100, ge=1, le=10000)


class CouponUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    code: Optional[str] = Field(default=None, min_length=3, max_length=100)
    category_id: Optional[int] = None
    valid_from: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    valid_to: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    is_active: Optional[bool] = None
    max_uses: Optional[int] = Field(default=None, ge=1, le=10000)


class CouponAdminOut(BaseModel):
    id: int
    name: str
    code: str
    discount_percent: int
    service_slug: str
    category_id: int
    category_name: Optional[str] = None
    valid_from: str
    valid_to: str
    is_active: bool
    max_uses: int
    redemption_count: int = 0
    eligibility_count: int = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CouponEligibilityOut(BaseModel):
    id: int
    line_user_id: str
    client_name: Optional[str] = None
    created_at: Optional[datetime] = None


class CouponEligibilityAddRequest(BaseModel):
    line_user_ids: List[str] = Field(min_length=1)


class AdminClientOut(BaseModel):
    id: int
    line_user_id: str
    last_name: str
    first_name: str
    create_date: Optional[datetime] = None

    class Config:
        from_attributes = True


class CouponValidateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    line_user_id: str = Field(min_length=1, max_length=50)
    category: str = Field(min_length=1, max_length=50)
    base_price: int = Field(ge=0)


class CouponValidateOut(BaseModel):
    code: str
    name: str
    discount_percent: int
    original_price: int
    discounted_price: int
    message: str


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