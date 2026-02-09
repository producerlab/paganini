from aiogram import Bot, Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy.ext.asyncio import AsyncSession

from filters.chat_types import ChatTypeFilter, IsAdmin
from keyboards.admin_keyboards import get_admin_reply_kb
from services.admin import orm_get_admin_list, orm_get_user_via_phone, orm_get_last_payments, orm_get_generations_top, \
    orm_get_last_registrations
from services.auth_service import orm_get_user
from services.payment import orm_add_payment, orm_add_generations, orm_this_month_bonus_exists
from services.logging import logger

admin_router = Router(name='admin_router')
admin_router.message.filter(ChatTypeFilter(['private']), IsAdmin())


class Phone(StatesGroup):
    get = State()

class Tg(StatesGroup):
    get = State()

class AddGenerations(StatesGroup):
    tg_id = State()
    amount = State()
    generations_number = State()


@admin_router.message(F.text.lower() == 'upd_adm')
async def cmd_upd_admin(msg: types.Message, bot: Bot, session: AsyncSession) -> None:
    """Command update admin list"""
    admins_list = await orm_get_admin_list(session=session)
    bot.admins_list = admins_list
    reply_text = f'Вы обновили список админов!'
    await msg.answer(
        text=reply_text,
        reply_markup=get_admin_reply_kb()
    )


@admin_router.message(F.text.lower().contains('adm'))
async def cmd_admin(msg: types.Message) -> None:
    """Command admin"""
    reply_text = f'Приветствую - {msg.from_user.first_name}!\n'
    reply_text += f'Вы в админ панели'
    await msg.answer(
        text=reply_text,
        reply_markup=get_admin_reply_kb()
    )


@admin_router.message(F.text == 'User по Тел')
async def cmd_user_info_phone(msg: types.Message, state: FSMContext) -> None:
    """Ask for user info via Phone"""
    reply_text = f'Введите номер пользователя, чтобы получить его данные!'
    await state.set_state(Phone.get)
    await msg.answer(
        text=reply_text,
        reply_markup=types.ReplyKeyboardRemove()
    )


@admin_router.message(Phone.get, F.text)
async def get_user_info_phone(msg: types.Message, state: FSMContext, session: AsyncSession):
    try:
        phone = int(msg.text.strip().replace('+', '').replace(' ', ''))
    except ValueError:
        await msg.answer(text='❌ Некорректный номер телефона. Введите только цифры.')
        return

    await state.clear()
    user = await orm_get_user_via_phone(session, phone)
    if user is not None:
        club_bonus = await orm_this_month_bonus_exists(session, user.tg_id)
        reply_text = f'Информация о пользователе:\n\n'
        reply_text += f'Имя: {user.first_name}\n'
        reply_text += f'Роль: {user.role}\n'
        reply_text += f'TG id: {user.tg_id}\n'
        reply_text += f'Телефон: +{user.phone}\n'
        reply_text += f'Email: {user.email}\n'
        reply_text += f'Сделал отчетов: {user.generations_made}\n'
        reply_text += f'Осталось генераций: {user.generations_left}\n'
        reply_text += f'Бонусов заработано: {user.bonus_total}\n'
        reply_text += f'Бонусов доступно: {user.bonus_left}\n'
        reply_text += f'Клубный бонус: {"✅ получен" if club_bonus else "❌ не получен"}'
    else:
        reply_text = f'Пользователя с номером +{phone} нету!'
    await msg.answer(
        text=reply_text,
        reply_markup=get_admin_reply_kb()
    )


@admin_router.message(F.text == 'User по TG')
async def cmd_user_info_tg(msg: types.Message, state: FSMContext) -> None:
    """Ask for user info via Tg"""
    reply_text = f'Введите телеграм id пользователя, чтобы получить его данные!'
    await state.set_state(Tg.get)
    await msg.answer(
        text=reply_text,
        reply_markup=types.ReplyKeyboardRemove()
    )


@admin_router.message(Tg.get, F.text)
async def get_user_info_by_tg(msg: types.Message, state: FSMContext, session: AsyncSession):
    try:
        tg_id = int(msg.text.strip())
    except ValueError:
        await msg.answer(text='❌ Некорректный Telegram ID. Введите только цифры.')
        return

    await state.clear()
    user = await orm_get_user(session, tg_id)
    if user is not None:
        club_bonus = await orm_this_month_bonus_exists(session, user.tg_id)
        reply_text = f'Информация о пользователе:\n\n'
        reply_text += f'Имя: {user.first_name}\n'
        reply_text += f'Роль: {user.role}\n'
        reply_text += f'TG id: {user.tg_id}\n'
        reply_text += f'Телефон: +{user.phone}\n'
        reply_text += f'Email: {user.email}\n'
        reply_text += f'Сделал отчетов: {user.generations_made}\n'
        reply_text += f'Осталось генераций: {user.generations_left}\n'
        reply_text += f'Бонусов заработано: {user.bonus_total}\n'
        reply_text += f'Бонусов доступно: {user.bonus_left}\n'
        reply_text += f'Клубный бонус: {"✅ получен" if club_bonus else "❌ не получен"}'
    else:
        reply_text = f'Пользователя с tg_id {tg_id} нету!'
    await msg.answer(
        text=reply_text,
        reply_markup=get_admin_reply_kb()
    )


@admin_router.message(F.text == 'Добавить платеж')
async def cmd_add_payment(msg: types.Message, state: FSMContext) -> None:
    """Add payment"""
    reply_text = f'Введите Telegram id пользователя, которому Вы хотите добавить платеж!'
    await state.set_state(AddGenerations.tg_id)
    await msg.answer(
        text=reply_text,
        reply_markup=types.ReplyKeyboardRemove()
    )


@admin_router.message(AddGenerations.tg_id, F.text)
async def get_payment_tg_id(msg: types.Message, state: FSMContext):
    try:
        tg_id = int(msg.text.strip())
    except ValueError:
        await msg.answer(text='❌ Некорректный Telegram ID. Введите только цифры.')
        return

    await state.update_data(tg_id=tg_id)
    reply_text = f'Введите сумму платежа!'
    await state.set_state(AddGenerations.amount)
    await msg.answer(text=reply_text)


@admin_router.message(AddGenerations.amount, F.text)
async def get_payment_amount(msg: types.Message, state: FSMContext):
    try:
        amount = int(msg.text.strip())
    except ValueError:
        await msg.answer(text='❌ Некорректная сумма. Введите только цифры.')
        return

    await state.update_data(amount=amount)
    reply_text = f'Введите количество генераций!'
    await state.set_state(AddGenerations.generations_number)
    await msg.answer(text=reply_text)


@admin_router.message(AddGenerations.generations_number, F.text)
async def get_payment_generations(msg: types.Message, state: FSMContext, session: AsyncSession):
    try:
        generations_num = int(msg.text.strip())
    except ValueError:
        await msg.answer(text='❌ Некорректное количество. Введите только цифры.')
        return

    await state.update_data(generations_num=generations_num)
    data = await state.get_data()
    await orm_add_generations(session=session, tg_id=data['tg_id'], generations_num=data['generations_num'])
    await orm_add_payment(
        session=session,
        tg_id=data['tg_id'],
        amount=data['amount'],
        generations_num=data['generations_num'],
        source='GC',
        yoo_id=''
    )
    reply_text = f'Пользователю {data["tg_id"]} добавлен платеж:\n'
    reply_text += f'Сумма - {data["amount"]}\nГенераций - {data["generations_num"]}'
    await state.clear()
    await msg.answer(
        text=reply_text,
        reply_markup=get_admin_reply_kb()
    )


@admin_router.message(F.text == 'Последние платежи')
async def show_last_payments(msg: types.Message, session: AsyncSession) -> None:
    """Last payments"""
    payments = await orm_get_last_payments(session=session, number=10)
    reply_text = f'Последние 10 платежей:\n'
    for payment in payments:
        reply_text += f'\nДата - {payment.created}'
        reply_text += f'\nИсточник - {payment.source}'
        reply_text += f'\nTg-id - {payment.tg_id}'
        reply_text += f'\nСумма - {payment.amount}'
        reply_text += f'\nГенераций - {payment.generations_num}\n'
    await msg.answer(text=reply_text)


@admin_router.message(F.text == 'Топ по генерациям')
async def show_generations_top(msg: types.Message, session: AsyncSession) -> None:
    """Generations top"""
    users = await orm_get_generations_top(session=session, number=20)
    reply_text = f'Топ 20 пользователей по кол-ву генераций:\n'
    for user in users:
        reply_text += f'\nИмя: {user.first_name}\n'
        reply_text += f'TG id: {user.tg_id}\n'
        reply_text += f'Телефон: +{user.phone}\n'
        reply_text += f'Сделал отчетов: {user.generations_made}\n'
        reply_text += f'Осталось генераций: {user.generations_left}\n'
    await msg.answer(text=reply_text)


@admin_router.message(F.text == 'Последние реги')
async def show_last_registrations(msg: types.Message, session: AsyncSession) -> None:
    """Last registrations"""
    users = await orm_get_last_registrations(session=session, number=20)
    reply_text = f'Последние регистрации:\n'
    for user in users:
        reply_text += f'\n#{user.id} {user.first_name}\n'
        reply_text += f'TG id: {user.tg_id}\n'
        reply_text += f'Телефон: +{user.phone}\n'
        reply_text += f'Сделал отчетов: {user.generations_made}\n'
        reply_text += f'Осталось генераций: {user.generations_left}\n'
    await msg.answer(text=reply_text)


@admin_router.message(Command('add_gens'))
async def cmd_add_gens(msg: types.Message, session: AsyncSession) -> None:
    """
    Быстрое добавление генераций пользователю.
    Формат: /add_gens <tg_id> <количество>
    Пример: /add_gens 123456789 100
    """
    args = msg.text.split()[1:]  # Убираем саму команду

    if len(args) != 2:
        await msg.answer(
            '❌ Неверный формат.\n\n'
            'Использование: /add_gens <tg_id> <количество>\n'
            'Пример: /add_gens 123456789 100'
        )
        return

    try:
        tg_id = int(args[0])
        amount = int(args[1])
    except ValueError:
        await msg.answer('❌ tg_id и количество должны быть числами.')
        return

    if amount <= 0:
        await msg.answer('❌ Количество генераций должно быть больше 0.')
        return

    # Проверяем существование пользователя
    user = await orm_get_user(session, tg_id)
    if user is None:
        await msg.answer(f'❌ Пользователь с tg_id {tg_id} не найден.')
        return

    # Добавляем генерации
    await orm_add_generations(session=session, tg_id=tg_id, generations_num=amount)

    logger.info(f'Админ {msg.from_user.id} добавил {amount} генераций пользователю {tg_id}')

    await msg.answer(
        f'✅ Готово!\n\n'
        f'Пользователю {user.first_name} (tg_id: {tg_id})\n'
        f'добавлено генераций: {amount}\n\n'
        f'Было: {user.generations_left}\n'
        f'Стало: {user.generations_left + amount}',
        reply_markup=get_admin_reply_kb()
    )
