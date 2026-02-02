from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import User
from services.logging import logger


async def orm_get_user(session: AsyncSession, tg_id: int):
    query = select(User).options(selectinload(User.selected_store)).where(User.tg_id == tg_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()

async def orm_check_user_reg(session: AsyncSession, tg_id: int):
    user = await orm_get_user(session, tg_id)
    logger.debug(f"Check user registration: tg_id={tg_id}, found={user is not None}")
    return user is not None

async def orm_add_user(session: AsyncSession, user_data: dict):
    # Convert phone to int (remove any non-digit characters first)
    phone_str = str(user_data['phone']).replace('+', '').replace(' ', '').replace('-', '')
    phone_int = int(phone_str) if phone_str.isdigit() else 0

    obj = User(
        tg_id=user_data['tg_id'],
        phone=phone_int,
        first_name=user_data['first_name'],
        user_name=user_data.get('user_name'),
    )
    session.add(obj)
    await session.commit()