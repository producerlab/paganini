from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Store, User
from services.crypto import encrypt_token, decrypt_token


async def orm_add_store(session: AsyncSession, store_data: dict):
    # Encrypt token before storing
    encrypted_token = encrypt_token(store_data['token'])

    obj = Store(
        tg_id=store_data['tg_id'],
        name=store_data['name'],
        token=encrypted_token,
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


async def orm_check_store_owner(session: AsyncSession, store_id: int, tg_id: int) -> bool:
    """Check if the store belongs to the user"""
    query = select(Store).where(Store.id == store_id, Store.tg_id == tg_id)
    result = await session.execute(query)
    return result.scalar_one_or_none() is not None


async def orm_edit_store(session: AsyncSession, store_data: dict):
    # Encrypt token before storing
    encrypted_token = encrypt_token(store_data['token'])

    query = update(Store).where(Store.id == store_data['store_id']).values(name = store_data['name'], token = encrypted_token)
    await session.execute(query)
    await session.commit()


async def orm_edit_store_name(session: AsyncSession, store_id: int, name: str):
    """Update only the store name"""
    query = update(Store).where(Store.id == store_id).values(name=name)
    await session.execute(query)
    await session.commit()


async def orm_edit_store_token(session: AsyncSession, store_id: int, token: str):
    """Update only the store token"""
    encrypted_token = encrypt_token(token)
    query = update(Store).where(Store.id == store_id).values(token=encrypted_token)
    await session.execute(query)
    await session.commit()


async def orm_delete_store(session: AsyncSession, store_id: int, tg_id: int):
    """Delete a store and update user's selected_store if needed"""
    # First check if this is the user's selected store
    user_query = select(User).where(User.tg_id == tg_id)
    user_result = await session.execute(user_query)
    user = user_result.scalar_one_or_none()

    # Delete the store
    delete_query = delete(Store).where(Store.id == store_id, Store.tg_id == tg_id)
    await session.execute(delete_query)

    # If deleted store was selected, reset selection
    if user and user.selected_store_id == store_id:
        # Try to select another store or set to None
        other_store_query = select(Store).where(Store.tg_id == tg_id, Store.id != store_id).limit(1)
        other_store_result = await session.execute(other_store_query)
        other_store = other_store_result.scalar_one_or_none()

        new_store_id = other_store.id if other_store else None
        update_user_query = update(User).where(User.tg_id == tg_id).values(selected_store_id=new_store_id)
        await session.execute(update_user_query)

    await session.commit()


def get_decrypted_token(store: Store) -> str:
    """Get decrypted token from a Store object."""
    return decrypt_token(store.token)


async def orm_set_store(session: AsyncSession, tg_id: int, store_id: int):
    query = update(User).where(User.tg_id == tg_id).values(selected_store_id = store_id)
    await session.execute(query)
    await session.commit()
