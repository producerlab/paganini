import os
from sqlalchemy import select, update, exists
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Ref, User
from services.payment import orm_add_payment


async def generate_referral_link(user_id: int) -> str:
    return f"https://t.me/{os.getenv('BOT_USERNAME')}?start=ref_{user_id}"


async def orm_save_ref(session: AsyncSession, referrer_id: int, referral_id: int):
    query = select(exists().where(Ref.referral_id == referral_id))
    result = await session.execute(query)
    if not result.scalar():
        obj = Ref(
            referrer_id=referrer_id,
            referral_id=referral_id,
        )
        session.add(obj)
        await session.commit()


async def orm_get_refs(session: AsyncSession, user_id: int) -> list[str]:
    query = (
        select(User.phone, User.first_name)
        .join(Ref, User.tg_id == Ref.referral_id)
        .where(Ref.referrer_id == user_id)
    )
    result = await session.execute(query)
    referrals = result.all()

    return [f"{phone} - {first_name}" for phone, first_name in referrals]


async def orm_get_referrer(session: AsyncSession, referral_id: int):
    query = select(Ref.referrer_id).where(Ref.referral_id == referral_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def orm_add_bonus(session: AsyncSession, tg_id: int, amount: int):
    bonus = amount // 10
    query = update(User).where(User.tg_id == tg_id).values(
        bonus_left=User.bonus_left+bonus,
        bonus_total=User.bonus_total+bonus
    )
    await session.execute(query)
    await session.commit()


async def orm_get_gens_for_bonus(session: AsyncSession, tg_id: int, amount: int, gens_num: int):
    """Обмен бонусов на генерации."""
    # Начисляем генерации пользователю
    query_gens = update(User).where(User.tg_id == tg_id).values(
        generations_left=User.generations_left + gens_num
    )
    await session.execute(query_gens)

    # Списываем бонусы
    query_bonus = update(User).where(User.tg_id == tg_id).values(
        bonus_left=User.bonus_left - amount
    )
    await session.execute(query_bonus)

    # Записываем платёж (с amount=0, source='bonus')
    await orm_add_payment(session, tg_id, 0, gens_num, 'bonus', yoo_id=None)

    # Один commit для всей транзакции (orm_add_payment делает commit внутри)
