import re

from aiogram import Router, types, F, Bot
from aiogram.filters import Command, or_f, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from keyboards.user_keyboards import get_main_kb, get_payment_kb, get_payment_check_kb
from services.logging import logger

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
from services.auth_service import orm_get_user
from services.payment import create_payment, check_payment, orm_check_payment_exists, orm_add_payment, \
    orm_add_generations, orm_get_email, orm_set_email, orm_this_month_bonus_exists, check_user_in_club
from services.refs import orm_get_referrer, orm_add_bonus

user_router = Router(name="user_router")


@user_router.message(or_f(Command("profile"), (F.text.lower().contains('профиль')), (F.text.lower().contains('кабинет'))))
async def cmd_profile(msg: types.Message, session: AsyncSession) -> None:
    """Command profile"""
    tg_id = msg.from_user.id
    await handle_profile(msg, tg_id, session)


@user_router.callback_query(F.data == 'cb_btn_profile')
async def cb_profile(callback: types.CallbackQuery, session: AsyncSession) -> None:
    """Callback profile"""
    tg_id = callback.from_user.id
    await handle_profile(callback.message, tg_id, session)
    await callback.answer()


async def handle_profile(msg: types.Message, tg_id:int, session: AsyncSession) -> None:
    user = await orm_get_user(session, tg_id)
    reply_text = '📌 <b>Профиль:</b>\n\n'
    reply_text += f'👤 <b>Имя:</b> {user.first_name}\n'
    reply_text += f'🆔 <b>Телеграм id:</b> {user.tg_id}\n'
    reply_text += f'📞 <b>Телефон:</b> +{user.phone}\n\n'
    reply_text += f'📊 <b>Отчетов доступно:</b> {user.generations_left}\n'
    reply_text += f'<b>       Сделано:</b> {user.generations_made}\n'
    reply_text += f'💎 <b>Бонусов доступно:</b> {user.bonus_left}\n'
    reply_text += f'<b>       Заработано:</b> {user.bonus_total}\n'
    await msg.answer(
        text=reply_text,
        reply_markup=get_main_kb(),
        parse_mode='HTML'
    )


@user_router.callback_query(F.data == 'cb_btn_bonus')
async def cb_bonus(callback: types.CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    """Command get club bonus"""
    if not await check_user_in_club(callback.from_user.id, bot):
        reply_text = ('❌ Бонус доступен ежемесячно только для резидентов закрытого клуба Titan Sellers Club\n\n'
                        'Если вы еще не резидент, напишите нам в поддержку @mpbiz_bot')
    elif await orm_this_month_bonus_exists(session, callback.from_user.id):
        reply_text = '❌ Вы уже получали бонус в этом месяце'
    else:
        await orm_add_generations(session, callback.from_user.id, 4)
        await orm_add_payment(
            session=session,
            tg_id=callback.from_user.id,
            amount=0,
            generations_num=4,
            source='Club',
            yoo_id=''
        )
        reply_text = '✅ Вам начислено 4 бонусных генерации!'
    await callback.answer()
    await callback.message.answer(
        text=reply_text,
        reply_markup=get_main_kb()
    )


@user_router.callback_query(F.data == 'cb_btn_payment')
async def cb_payment(callback: types.CallbackQuery) -> None:
    """Command payment"""
    reply_text = (
        '💳 <b>Тарифы и цены</b>\n\n'
        '📦 <b>Разовый</b>\n'
        '├─ 🔁 Генераций: 1\n'
        '├─ 💰 Цена: 490 ₽\n'
        '└─ 📊 За генерацию: 490 ₽\n\n'

        '📅 <b>Месяц</b>\n'
        '├─ 🔁 Генераций: 4\n'
        '├─ 💰 Цена: 1 690 ₽\n'
        '└─ 📊 За генерацию: 423 ₽\n\n'

        '🗓 <b>Квартал</b>\n'
        '├─ 🔁 Генераций: 12\n'
        '├─ 💰 Цена: 4 990 ₽\n'
        '└─ 📊 За генерацию: 416 ₽\n\n'

        '📆 <b>Год</b>\n'
        '├─ 🔁 Генераций: 52\n'
        '├─ 💰 Цена: 17 990 ₽\n'
        '└─ 📊 За генерацию: 346 ₽'
    )
    await callback.answer()
    await callback.message.answer(
        text=reply_text,
        reply_markup=get_payment_kb(),
        parse_mode='HTML'
    )


class Email(StatesGroup):
    get = State()


@user_router.callback_query(F.data.startswith('payfor_'))
async def cb_pay_for(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    email = await orm_get_email(session, callback.from_user.id)
    if email is None:
        await state.set_state(Email.get)
        await callback.message.answer(
            text=(
                '📧 <b>Куда отправить чек после оплаты?</b>\n\n'
                'Email нужен для:\n'
                '• Отправки чека об оплате\n'
                '• Восстановления доступа при необходимости\n\n'
                'Введите ваш email:'
            ),
            reply_markup=get_main_kb(),
            parse_mode='HTML'
        )
    else:
        data = callback.data.split('_', 2)
        generations_num = data[1]
        amount = data[2]
        payment_url, payment_id = create_payment(callback.from_user.id, generations_num, amount, email)
        reply_text = 'Ваша ссылка на оплату:\n'
        reply_text += f'{payment_url}\n\n'
        reply_text += 'После того как проведете оплату нажмите на кнопку 👇, чтобы проверить платеж'
        await callback.message.answer(
            text=reply_text,
            reply_markup=get_payment_check_kb(payment_id)
        )


@user_router.message(Email.get, F.text)
async def get_email(msg: types.Message, state: FSMContext, session: AsyncSession):
    email = msg.text.strip().lower()
    if EMAIL_REGEX.match(email):
        logger.debug(f"User {msg.from_user.id} set email: {email}")
        await orm_set_email(session, msg.from_user.id, email)
        await state.clear()
        await msg.answer(
            text='✅ E-mail для чеков сохранен, повторно выберите интересующий Вас тариф',
            reply_markup=get_payment_kb()
        )
    else:
        await msg.answer(text='❌ E-mail некорректен, введите еще раз')


@user_router.message(StateFilter(Email.get),~F.text)
async def not_email(msg: types.Message):
    await msg.answer(text='❌ Вы ввели не E-mail, попробуйте еще раз')


@user_router.callback_query(F.data.startswith('checkpayment_'))
async def cb_check_payment(callback: CallbackQuery, session: AsyncSession):
    payment_id = callback.data.split('_', 1)[1]
    result = check_payment(payment_id)
    if await orm_check_payment_exists(session, payment_id):
        reply_text = '❌ Вы уже получили генерации за этот платеж'
    elif result:
        generations_num = int(result['generations_num'])
        tg_id = int(result['user_id'])
        amount = int(float(result['amount']))
        referrer = await orm_get_referrer(session, tg_id)
        if referrer is not None:
            await orm_add_bonus(session, referrer, amount)
        await orm_add_generations(session, tg_id, generations_num)
        await orm_add_payment(
            session=session,
            tg_id=tg_id,
            amount=amount,
            generations_num=generations_num,
            source='bot',
            yoo_id=payment_id
        )
        reply_text = f'✅ Оплата прошла успешно, Вам добавлено {generations_num} генераций\n\n'
    else:
        reply_text = '❌ Платеж еще не прошел'
    await callback.message.answer(
        text=reply_text,
        reply_markup=get_main_kb()
    )