from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Store, User


async def orm_add_store(session: AsyncSession, store_data: dict):
    obj = Store(
        tg_id=store_data['tg_id'],
        name=store_data['name'],
        token=store_data['token'],
    )
    session.add(obj)
    await session.commit()
    store_id = obj.id
    query = update(User).where(User.tg_id == store_data['tg_id']).values(selected_store_id = store_id)
    await session.execute(query)
    await session.commit()


async def orm_get_user_stores(session: AsyncSession, tg_id: int):
    query = select(Store).where(Store.tg_id == tg_id)
    result = await session.execute(query)
    return result.scalars().all()


async def orm_get_store(session: AsyncSession, id: int):
    query = select(Store).where(Store.id == id)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def orm_edit_store(session: AsyncSession, store_data: dict):
    query = update(Store).where(Store.id == store_data['store_id']).values(name = store_data['name'], token = store_data['token'])
    await session.execute(query)
    await session.commit()


async def orm_set_store(session: AsyncSession, tg_id: int, store_id: int):
    query = update(User).where(User.tg_id == tg_id).values(selected_store_id = store_id)
    await session.execute(query)
    await session.commit()
