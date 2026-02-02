from datetime import datetime

import yookassa
import uuid
import os
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from sqlalchemy import update, select, exists
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Payment
from services.auth_service import orm_get_user

yookassa.Configuration.configure(f'{os.getenv("UKASSA_ACCOUNT_ID")}', f'{os.getenv("UKASSA_SECRET_KEY")}')


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


def create_payment(tg_id, generations_num, amount, email):
    id_key = str(uuid.uuid4())
    return_url = f'https://t.me/{os.getenv("BOT_USERNAME")}'
    payment = yookassa.Payment.create(
    {
        'amount': {
            'value': amount,
            'currency': "RUB"
        },
        'confirmation': {
            'type': 'redirect',
            'return_url': return_url
        },
        'capture': True,
        'description': 'Оплата генераций отчетов в боте Paganini',
        'metadata': {
            'user_id': tg_id,
            'generations_num': generations_num,
            'amount': amount
        },
        'receipt': {
            'customer': {
                'email': email
            },
            'items': [
                {
                  'description': f'Оплата генераций отчетов в боте Paganini: {generations_num}',
                  'quantity': 1,
                  'amount': {
                    'value': amount,
                    'currency': 'RUB'
                  },
                  "vat_code": 1,
                  "payment_mode": "full_prepayment",
                  "payment_subject": "commodity"
                },
            ]
        }
    }, id_key)

    return payment.confirmation.confirmation_url, payment.id


def check_payment(payment_id):
    payment = yookassa.Payment.find_one(payment_id)
    if payment.status == 'succeeded':
        return payment.metadata
    else:
        return False


async def orm_check_payment_exists(session: AsyncSession, yoo_id: str) -> bool:
    query = select(exists().where(Payment.yoo_id == yoo_id))
    result = await session.execute(query)
    return result.scalar()


async def orm_add_generations(session: AsyncSession, tg_id: int, generations_num: int):
    query = update(User).where(User.tg_id == tg_id).values(generations_left=User.generations_left + generations_num)
    await session.execute(query)
    await session.commit()


async def orm_add_payment(session: AsyncSession, tg_id: int, amount: int, generations_num: int, source:str, yoo_id: str):
    obj = Payment(
        tg_id=tg_id,
        amount=amount,
        generations_num=generations_num,
        source=source,
        yoo_id=yoo_id
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