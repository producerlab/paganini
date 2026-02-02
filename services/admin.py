from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Payment


async def orm_get_admin_list(session: AsyncSession):
    query = select(User.tg_id).where(User.role == 'admin')
    result = await session.execute(query)
    admins_list = [el[0] for el in result]
    return admins_list


async def orm_get_user_via_phone(session: AsyncSession, phone: int):
    query = select(User).where(User.phone == phone)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def orm_get_last_payments(session: AsyncSession, number: int):
    query = select(Payment).order_by(Payment.id.desc()).limit(number)
    result = await session.execute(query)
    return result.scalars().all()


async def orm_get_generations_top(session: AsyncSession, number: int):
    query = select(User).order_by(User.generations_made.desc()).limit(number)
    result = await session.execute(query)
    return result.scalars().all()


async def orm_get_last_registrations(session: AsyncSession, number: int):
    query = select(User).order_by(User.id.desc()).limit(number)
    result = await session.execute(query)
    return result.scalars().all()