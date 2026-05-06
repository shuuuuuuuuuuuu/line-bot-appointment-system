from pydantic import BaseModel
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

    class Config:
        from_attributes = True