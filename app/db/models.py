from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey, TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base

class Admin(Base):
    __tablename__ = "admins"
    __table_args__ = {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Client(Base):
    __tablename__ = "clients"
    __table_args__ = {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    
    id = Column(Integer, primary_key=True, index=True)
    line_user_id = Column(String(50), unique=True, index=True)
    last_name = Column(String(50), nullable=False)
    first_name = Column(String(50), nullable=False)
    create_date = Column(TIMESTAMP, server_default=func.now())
    
    appointments = relationship("Appointment", back_populates="client")

class Category(Base):
    __tablename__ = 'categories'
    __table_args__ = {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    id = Column(Integer, primary_key=True)
    category_name = Column(String(50), nullable=False)

    services = relationship("Service", back_populates="category", cascade="all, delete-orphan")

class Service(Base):
    __tablename__ = "services"
    __table_args__ = {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    
    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String(255), nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False)
    price = Column(Integer, nullable=False, default=0)
    duration_minutes = Column(Integer, nullable=False, default=60)
    is_active = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)

    category = relationship("Category", back_populates="services")
    appointment_items = relationship("AppointmentItem", back_populates="service")

class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    total_price = Column(Integer) 
    paid = Column(Boolean, default=False)
    service_dateTime = Column(DateTime)
    total_duration = Column(Integer)
    expired = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user_message = Column(String(500), nullable=True)
    payment_deadline_at = Column(DateTime, nullable=True)
    payment_proof_received = Column(Boolean, default=False)
    payment_reminder_sent = Column(Boolean, default=False)
    owner_notified = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)
    google_event_id = Column(String(255), nullable=True)
    
    client = relationship("Client", back_populates="appointments")
    items = relationship("AppointmentItem", back_populates="appointment")

class AppointmentItem(Base):
    __tablename__ = "appointment_items"
    __table_args__ = {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    
    id = Column(Integer, primary_key=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"))
    service_id = Column(Integer, ForeignKey("services.id"))

    appointment = relationship("Appointment", back_populates="items")
    service = relationship("Service", back_populates="appointment_items")

class MessageTemplate(Base):
    __tablename__ = "message_templates"
    __table_args__ = {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(64), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    body = Column(String(4000), nullable=False)
    description = Column(String(500), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    category = relationship("Category")


class BusinessSetting(Base):
    __tablename__ = "business_settings"
    __table_args__ = {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}

    id = Column(Integer, primary_key=True)
    open_hour = Column(Integer, nullable=False, default=9)
    close_hour = Column(Integer, nullable=False, default=21)
    slot_interval_minutes = Column(Integer, nullable=False, default=60)
    buffer_minutes = Column(Integer, nullable=False, default=60)
    # JSON array of Python weekdays: Mon=0 ... Sun=6
    off_weekdays = Column(String(64), nullable=False, default="[4,5,6]")
    max_advance_days = Column(Integer, nullable=False, default=30)
    slot_lock_minutes = Column(Integer, nullable=False, default=10)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class BusinessHoliday(Base):
    __tablename__ = "business_holidays"
    __table_args__ = {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}

    id = Column(Integer, primary_key=True)
    holiday_date = Column(Date, nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
