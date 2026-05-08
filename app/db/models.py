from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base

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