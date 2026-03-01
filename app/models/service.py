import uuid
from datetime import datetime, time
from decimal import Decimal
from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey, Numeric, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
from sqlalchemy.orm import relationship


class Service(Base):
    __tablename__ = "services"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.businesses.id"), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), nullable=False)
    service_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Dhaka")
    base_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Operating hours for this service
    open_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    close_time: Mapped[time | None] = mapped_column(Time, nullable=True)

    # Additional fields
    category: Mapped[str | None] = mapped_column(String(50), nullable=True, default="GENERAL")
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_popular: Mapped[bool] = mapped_column(Boolean, default=False)
    service_type: Mapped[str] = mapped_column(String(20), default="IN_PERSON")
    max_capacity: Mapped[int | None] = mapped_column(Integer, nullable=True, default=1)
    allow_multiple_bookings: Mapped[bool] = mapped_column(Boolean, default=False)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    business = relationship("Business", back_populates="services")
    bookings = relationship("Booking", back_populates="service")
    images = relationship("ServiceImage", back_populates="service")
    capacity_rule = relationship("ServiceCapacityRule", back_populates="service", uselist=False)
    contact = relationship(
    "ServiceContact",
    back_populates="service",
    uselist=False,
    cascade="all, delete-orphan",
)   
