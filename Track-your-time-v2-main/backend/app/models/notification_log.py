# from app.models import User
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    push_token: Mapped[str] = mapped_column(String(2000), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    push_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship(back_populates="devices", foreign_keys=[user_id])


class NotificationLog(Base):
    __tablename__ = "notifications_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    channel: Mapped[str] = mapped_column(String(50), default="push")
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    action: Mapped[str | None] = mapped_column(String(50), nullable=True)
    client_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    device_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True)
