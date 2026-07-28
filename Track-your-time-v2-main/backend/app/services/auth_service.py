import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.models import User

# bcrypt is deliberately slow — that is the point of a password hash — but it is
# also pure blocking CPU. Called directly inside an `async def`, a single hash
# stalls the entire event loop for 100-400ms, which means EVERY other in-flight
# request on the server waits for one user's login to finish hashing.
# asyncio.to_thread moves it to a worker thread so the loop stays responsive.


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, email: str, password: str, timezone: str) -> User:
    hashed = await asyncio.to_thread(hash_password, password)
    user = User(email=email, hashed_password=hashed, timezone=timezone)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(db, email)
    if not user:
        return None
    ok = await asyncio.to_thread(verify_password, password, user.hashed_password)
    if not ok:
        return None
    return user


def issue_tokens(user: User) -> tuple[str, str]:
    return create_access_token(user.id), create_refresh_token(user.id)
