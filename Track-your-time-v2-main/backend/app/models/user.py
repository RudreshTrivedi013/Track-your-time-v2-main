import uuid
from datetime import datetime, time

from sqlalchemy import String, DateTime, Time, ForeignKey, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)

    primary_device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", use_alter=True, name="fk_user_primary_device"), nullable=True
    )

    quiet_hours_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    quiet_hours_end: Mapped[time | None] = mapped_column(Time, nullable=True)

    working_hours_start: Mapped[time] = mapped_column(Time, nullable=False, default=time(9, 0))
    working_hours_end: Mapped[time] = mapped_column(Time, nullable=False, default=time(17, 0))
    checkin_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    
    daily_summary_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reminders_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    checkin_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    tasks: Mapped[list["Task"]] = relationship(back_populates="user", cascade="all, delete-orphan", foreign_keys="Task.user_id")
    devices: Mapped[list["Device"]] = relationship(back_populates="user", cascade="all, delete-orphan", foreign_keys="Device.user_id")
