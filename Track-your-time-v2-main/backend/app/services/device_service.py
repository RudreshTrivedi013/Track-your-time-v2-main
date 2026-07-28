from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, User


async def pick_target_devices(db: AsyncSession, user: User) -> list[Device]:
    """Return ALL push-enabled devices for the user.

    Web-only app: no single-device heuristics needed — push to every
    registered browser session simultaneously.
    """
    result = await db.execute(
        select(Device).where(Device.user_id == user.id, Device.push_enabled.is_(True))
    )
    return list(result.scalars().all())


async def other_devices(db: AsyncSession, user_id, exclude_device_id) -> list[Device]:
    result = await db.execute(select(Device).where(Device.user_id == user_id))
    devices = list(result.scalars().all())
    return [d for d in devices if d.id != exclude_device_id]
