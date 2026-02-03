import re

from aiogram import Router, types, F, Bot
from aiogram.filters import Command, or_f, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from keyboards.user_keyboards import get_main_kb, get_payment_kb
from services.logging import logger

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
from services.auth_service import orm_get_user
from services.payment import (
    create_payment, orm_add_payment, orm_add_generations,
    orm_get_email, orm_set_email, orm_this_month_bonus_exists, check_user_in_club
)

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
        reply_text = (
            '💎 <b>Бонус для резидентов Titan Sellers Club</b>\n\n'
            'Каждый месяц участники клуба получают 4 бесплатных генерации отчетов!\n\n'
            '🚀 <b>Что даёт клуб Titan:</b>\n'
            '• Ежемесячные бонусы в Paganini\n'
            '• Закрытое сообщество селлеров\n'
            '• Эксклюзивные обучающие материалы\n'
            '• Прямая связь с экспертами'
        )
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        titan_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='🚀 Узнать о клубе Titan', url='https://marketplacebiz.ru/titanclub')],
            [InlineKeyboardButton(text='☰ Меню', callback_data='cb_btn_menu')]
        ])
        await callback.answer()
        await callback.message.answer(text=reply_text, reply_markup=titan_kb, parse_mode='HTML')
        return
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

        '⭐️ <b>Год</b> <i>— выгодный!</i>\n'
        '├─ 🔁 Генераций: 52\n'
        '├─ 💰 Цена: 17 990 ₽\n'
        '├─ 📊 За генерацию: <b>346 ₽</b>\n'
        '└─ 💎 Экономия: <b>7 490 ₽</b> (−29%)'
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
        # Сохраняем данные о тарифе в state для использования после ввода email
        data = callback.data.split('_', 2)
        await state.update_data(generations_num=data[1], amount=data[2])
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
        generations_num = int(data[1])
        amount = int(float(data[2]))  # float first, then int (handles "490.0")
        await process_payment_request(callback.message, callback.from_user.id, generations_num, amount, email)
    await callback.answer()


async def process_payment_request(message, tg_id: int, generations_num: int, amount: int, email: str):
    """Обработка запроса на создание платежа."""
    payment_url, result = await create_payment(tg_id, generations_num, amount, email)

    if payment_url:
        reply_text = (
            '💳 <b>Счёт на оплату создан!</b>\n\n'
            f'📦 Тариф: <b>{generations_num}</b> генераций\n'
            f'💰 Сумма: <b>{amount} ₽</b>\n\n'
            f'🔗 <a href="{payment_url}">Перейти к оплате</a>\n\n'
            '⏳ После оплаты генерации будут добавлены автоматически, '
            'и вы получите уведомление в этом чате.'
        )
        await message.answer(
            text=reply_text,
            reply_markup=get_main_kb(),
            parse_mode='HTML',
            disable_web_page_preview=True
        )
    else:
        # result содержит сообщение об ошибке
        logger.error(f"Ошибка создания платежа для {tg_id}: {result}")
        await message.answer(
            text='❌ Не удалось создать счёт на оплату. Пожалуйста, попробуйте позже или обратитесь в поддержку.',
            reply_markup=get_main_kb()
        )


@user_router.message(Email.get, F.text)
async def get_email(msg: types.Message, state: FSMContext, session: AsyncSession):
    email = msg.text.strip().lower()
    if EMAIL_REGEX.match(email):
        logger.debug(f"User {msg.from_user.id} set email: {email}")
        await orm_set_email(session, msg.from_user.id, email)

        # Получаем данные о тарифе из state
        state_data = await state.get_data()
        await state.clear()

        generations_num = state_data.get('generations_num')
        amount = state_data.get('amount')

        if generations_num and amount:
            # Сразу создаём платёж
            await msg.answer(text='✅ E-mail сохранён. Создаю счёт на оплату...')
            await process_payment_request(msg, msg.from_user.id, int(generations_num), int(float(amount)), email)
        else:
            # Если данных нет — просим выбрать тариф
            await msg.answer(
                text='✅ E-mail для чеков сохранен, выберите интересующий Вас тариф',
                reply_markup=get_payment_kb()
            )
    else:
        await msg.answer(text='❌ E-mail некорректен, введите еще раз')


@user_router.message(StateFilter(Email.get),~F.text)
async def not_email(msg: types.Message):
    await msg.answer(text='❌ Вы ввели не E-mail, попробуйте еще раз')


@user_router.callback_query(F.data.startswith('checkpayment_'))
async def cb_check_payment(callback: CallbackQuery, session: AsyncSession):
    """
    Legacy обработчик проверки платежа.

    С Модуль Банком платежи обрабатываются автоматически через webhook,
    но этот обработчик оставлен для обратной совместимости.
    """
    await callback.answer()
    await callback.message.answer(
        text=(
            '⏳ Платежи обрабатываются автоматически.\n\n'
            'Если вы уже оплатили, генерации будут добавлены в течение нескольких минут, '
            'и вы получите уведомление.\n\n'
            'Если прошло более 10 минут — обратитесь в поддержку.'
        ),
        reply_markup=get_main_kb()
    )