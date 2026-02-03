from datetime import datetime
from typing import Optional

import os
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from sqlalchemy import update, select, exists
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from database.models import User, Payment
from services.auth_service import orm_get_user
from services.logging import logger
from services import modulbank
from keyboards.user_keyboards import get_main_kb


async def orm_reduce_generations(session: AsyncSession, tg_id:int):
    query = update(User).where(User.tg_id == tg_id).values(
        generations_made=User.generations_made + 1,
        generations_left=User.generations_left - 1
    )
    await session.execute(query)
    await session.commit()


async def orm_get_email(session: AsyncSession, tg_id: int):
    user = await orm_get_user(session, tg_id)
    return user.email


async def orm_set_email(session: AsyncSession, tg_id: int, email: str):
    query = update(User).where(User.tg_id == tg_id).values(email=email)
    await session.execute(query)
    await session.commit()


async def create_payment(tg_id: int, generations_num: int, amount: int, email: str):
    """
    Создание платежа через Модуль Банк.

    Формат order_id: paganini_{tg_id}_{generations}_{amount}_{timestamp}

    Returns:
        Tuple (payment_url, bill_id) или (None, error_message)
    """
    import time
    custom_order_id = f"paganini_{tg_id}_{generations_num}_{amount}_{int(time.time())}"

    payment_url, bill_id, error = await modulbank.create_bill(
        email=email,
        amount=int(amount),
        generations_num=int(generations_num),
        tg_id=tg_id,
        custom_order_id=custom_order_id
    )

    if error:
        logger.error(f"Ошибка создания платежа для {tg_id}: {error}")
        return None, error

    return payment_url, bill_id


def parse_order_id(order_id: str) -> Optional[dict]:
    """
    Парсинг order_id для получения данных платежа.

    Формат: paganini_{tg_id}_{generations}_{amount}_{timestamp}
    """
    try:
        parts = order_id.split('_')
        if len(parts) >= 4 and parts[0] == 'paganini':
            return {
                'tg_id': int(parts[1]),
                'generations_num': int(parts[2]),
                'amount': int(parts[3])
            }
    except (ValueError, IndexError):
        pass
    return None


async def process_modulbank_payment(payment_data: dict, bot: Bot, session_maker: sessionmaker):
    """
    Обработка успешного платежа от webhook Модуль Банка.

    Вызывается из webhook_server.py при получении уведомления.

    ВАЖНО: Все операции выполняются в одной транзакции для атомарности.
    Порядок: сначала записываем платёж (для защиты от дубликатов),
    потом начисляем бонусы и генерации.
    """
    if not payment_data.get('is_success'):
        return

    order_id = payment_data.get('order_id', '')
    transaction_id = payment_data.get('transaction_id', '')

    # Парсим данные из order_id
    parsed = parse_order_id(order_id)
    if not parsed:
        logger.error(f"Не удалось распарсить order_id: {order_id}")
        return

    tg_id = parsed['tg_id']
    generations_num = parsed['generations_num']
    amount = parsed['amount']

    async with session_maker() as session:
        # Проверяем, не обработан ли уже этот платёж
        if await orm_check_modulbank_payment_exists(session, transaction_id):
            logger.warning(f"Платёж {transaction_id} уже обработан")
            return

        # === ВСЕ ОПЕРАЦИИ В ОДНОЙ ТРАНЗАКЦИИ ===

        # 1. Сначала записываем платёж (защита от дубликатов при повторных webhook)
        obj = Payment(
            tg_id=tg_id,
            amount=amount,
            generations_num=generations_num,
            source='bot',
            yoo_id=None,
            modulbank_bill_id=order_id,
            modulbank_transaction_id=transaction_id
        )
        session.add(obj)

        # 2. Добавляем генерации пользователю (без отдельного commit)
        query_gens = update(User).where(User.tg_id == tg_id).values(
            generations_left=User.generations_left + generations_num
        )
        await session.execute(query_gens)

        # 3. Обрабатываем реферальный бонус (без отдельного commit)
        from services.refs import orm_get_referrer
        referrer = await orm_get_referrer(session, tg_id)
        if referrer is not None:
            bonus = amount // 10  # 10% бонус
            query_bonus = update(User).where(User.tg_id == referrer).values(
                bonus_left=User.bonus_left + bonus,
                bonus_total=User.bonus_total + bonus
            )
            await session.execute(query_bonus)
            logger.info(f"Начислен бонус {bonus}₽ рефереру {referrer} от платежа {tg_id}")

        # 4. Один commit для всей транзакции
        await session.commit()

        logger.info(f"Платёж {transaction_id} обработан: {generations_num} генераций для {tg_id}")

    # Уведомляем пользователя
    try:
        await bot.send_message(
            tg_id,
            f'✅ Оплата прошла успешно!\n\n'
            f'Вам добавлено <b>{generations_num}</b> генераций отчётов.\n\n'
            f'Спасибо за покупку! 🎉',
            reply_markup=get_main_kb(),
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление пользователю {tg_id}: {e}")


async def orm_check_payment_exists(session: AsyncSession, yoo_id: str) -> bool:
    """Проверка существования платежа по YooKassa ID (legacy)."""
    query = select(exists().where(Payment.yoo_id == yoo_id))
    result = await session.execute(query)
    return result.scalar()


async def orm_check_modulbank_payment_exists(session: AsyncSession, transaction_id: str) -> bool:
    """Проверка существования платежа по Модуль Банк transaction_id."""
    query = select(exists().where(Payment.modulbank_transaction_id == transaction_id))
    result = await session.execute(query)
    return result.scalar()


async def orm_add_generations(session: AsyncSession, tg_id: int, generations_num: int):
    query = update(User).where(User.tg_id == tg_id).values(generations_left=User.generations_left + generations_num)
    await session.execute(query)
    await session.commit()


async def orm_add_payment(
    session: AsyncSession,
    tg_id: int,
    amount: int,
    generations_num: int,
    source: str,
    yoo_id: Optional[str] = None,
    modulbank_bill_id: Optional[str] = None,
    modulbank_transaction_id: Optional[str] = None
):
    """Добавление записи о платеже."""
    obj = Payment(
        tg_id=tg_id,
        amount=amount,
        generations_num=generations_num,
        source=source,
        yoo_id=yoo_id,
        modulbank_bill_id=modulbank_bill_id,
        modulbank_transaction_id=modulbank_transaction_id
    )
    session.add(obj)
    await session.commit()


async def orm_this_month_bonus_exists(session: AsyncSession, tg_id:int):
    start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    club_bonus_exist = (
        select(Payment)
        .where(
            Payment.tg_id == tg_id,
            Payment.source == "Club",
            Payment.created >= start_of_month
        )
        .limit(1)
    )

    result = await session.execute(club_bonus_exist)
    return result.scalar_one_or_none() is not None


async def check_user_in_club(tg_id: int, bot: Bot):
    club_chat_id = os.getenv('CLUB_CHAT_ID')
    if not club_chat_id:
        return False

    try:
        member = await bot.get_chat_member(int(club_chat_id), tg_id)
        is_member = member.status in ("member", "administrator", "creator")
    except TelegramBadRequest:
        # если бот не может получить статус — считаем не членом
        is_member = False

    return is_member