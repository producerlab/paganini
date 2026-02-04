import os

from aiogram import Router, types, F
from aiogram.filters import Command, or_f, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy.ext.asyncio import AsyncSession

from keyboards.user_keyboards import get_menu_kb, get_subscribe_kb, get_contact_reply_kb, get_main_kb, get_onboarding_kb
from services import auth_service
from services.refs import orm_save_ref
from services.logging import logger

common_router = Router(name="common_router")

# Channel for subscription check (from .env)
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME', '@khosnullin_channel')


class Registration(StatesGroup):
    contact = State()


class Onboarding(StatesGroup):
    step_store = State()  # Waiting for user to add store


@common_router.message(Command("start"))
async def cmd_start(msg: types.Message, state: FSMContext, session: AsyncSession) -> None:
    """Command start"""
    await state.clear()

    user_id = int(msg.from_user.id)
    is_registered = await auth_service.orm_check_user_reg(session, user_id)

    # Handle referral links
    if len(msg.text.split()) > 1:
        args = msg.text.split()[1]
        if args.startswith('ref_'):
            referrer_id = int(args.split('_')[1])
            logger.debug(f"Referral link used: referrer_id={referrer_id}")
            if referrer_id != msg.from_user.id:
                await orm_save_ref(session, referrer_id, msg.from_user.id)

    # Registered user - show menu
    if is_registered:
        reply_text = (
            f'🎻 <b>Paganini</b> — расшифровка финансовых отчётов WB\n\n'
            f'Приветствую, {msg.from_user.first_name}!\n\n'
            '☰ Меню:'
        )
        await msg.answer(
            text=reply_text,
            reply_markup=get_menu_kb(),
            parse_mode='HTML'
        )
        return

    # New user - check channel subscription first
    is_subscribed = True  # Default to True if check fails
    try:
        member = await msg.bot.get_chat_member(CHANNEL_USERNAME, user_id)
        is_subscribed = member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.warning(f"Cannot check subscription for {user_id}: {e}")

    if not is_subscribed:
        reply_text = (
            '🎻 <b>Paganini</b> — расшифровка финансовых отчётов WB\n\n'
            '✅ Понятная детализация вместо цифр в ЛК\n'
            '✅ Отчёт за 1 минуту\n'
            '✅ <b>4 генерации бесплатно</b>\n\n'
            f'Для доступа к боту подпишитесь на канал {CHANNEL_USERNAME}, '
            'затем нажмите на кнопку "Проверить подписку". 👇'
        )
        await msg.answer(
            text=reply_text,
            reply_markup=get_subscribe_kb(),
            parse_mode='HTML'
        )
    else:
        # New user, subscribed - ask for phone
        reply_text = (
            '🎻 <b>Paganini</b> — расшифровка финансовых отчётов WB\n\n'
            '✅ Понятная детализация вместо цифр в ЛК\n'
            '✅ Отчёт за 1 минуту\n'
            '✅ <b>4 генерации бесплатно</b>\n\n'
            'Для начала работы поделитесь своим контактом 👇'
        )
        await state.set_state(Registration.contact)
        await msg.answer(
            text=reply_text,
            reply_markup=get_contact_reply_kb(),
            parse_mode='HTML'
        )


@common_router.callback_query(F.data == 'check_subscription')
async def check_subscription(callback: types.CallbackQuery, state: FSMContext):
    try:
        member = await callback.bot.get_chat_member(CHANNEL_USERNAME, callback.from_user.id)
        is_subscribed = member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.warning(f"Cannot check subscription for {callback.from_user.id}: {e}")
        is_subscribed = True  # Allow if check fails

    if not is_subscribed:
        await callback.answer("❌ Вы ещё не подписаны.", show_alert=True)
    else:
        await state.set_state(Registration.contact)
        await callback.message.answer(
            text="Пожалуйста, поделитесь своим контактом.\nДля этого нажмите на кнопку внизу.👇",
            reply_markup=get_contact_reply_kb()
        )


@common_router.message(Registration.contact, F.contact)
async def add_user(msg: types.Message, state: FSMContext, session: AsyncSession):
    user_data = {
        'tg_id': msg.from_user.id,
        'phone': msg.contact.phone_number.lstrip('+'),
        'first_name': msg.from_user.first_name,
        'user_name': msg.from_user.username
    }
    await auth_service.orm_add_user(session, user_data)

    try:
        await msg.bot.delete_message(chat_id=msg.chat.id, message_id=msg.message_id-1)
    except Exception:
        pass  # Ignore if message already deleted

    # Start onboarding for new user
    reply_text = (
        '🎉 <b>Добро пожаловать в Paganini!</b>\n\n'
        'Давайте быстро настроим бота для работы.\n\n'
        '<b>Шаг 1:</b> Добавьте ваш магазин WB\n'
        'Для этого понадобится API-токен из личного кабинета.\n\n'
        '💡 <i>Первые 4 генерации отчетов — бесплатно!</i>'
    )
    await state.set_state(Onboarding.step_store)
    await msg.answer(
        text=reply_text,
        reply_markup=get_onboarding_kb(1),
        parse_mode='HTML'
    )


@common_router.message(StateFilter(Registration.contact),~F.contact)
async def check_contact(msg: types.Message):
    await msg.answer(
        text='Пожалуйста, поделитесь своим контактом.\nДля этого нажмите на кнопку внизу.👇👇👇',
        reply_markup=get_contact_reply_kb()
    )


@common_router.message(or_f(Command("menu"), (F.text.lower().contains('меню')), (F.text.lower().contains('menu'))))
async def cmd_menu(msg: types.Message, state: FSMContext) -> None:
    """Command menu"""
    await state.clear()
    await handle_menu(msg)


@common_router.callback_query(F.data == 'cb_btn_menu')
async def cb_menu(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Callback menu"""
    await state.clear()
    await handle_menu(callback.message)
    await callback.answer()


async def handle_menu(msg: types.Message) -> None:
    reply_text = '☰ Меню'
    await msg.answer(
        text=reply_text,
        reply_markup=get_menu_kb()
    )


@common_router.message(or_f(Command("about"), (F.text.lower().contains('о боте'))))
async def cmd_about(msg: types.Message, state: FSMContext) -> None:
    """Command about"""
    await state.clear()
    reply_text = 'Paganini – маэстро по расшифровке финансовых отчетов (еженедельной детализации) для селлеров на Wildberries\n\n'
    reply_text += 'Этот бот создавался профессиональными селлерами на Amazon, Wildberries, OZON и других маркетплейсах, которые собаку съели на финансовых расшифровках WB\n\n'
    reply_text += 'Благодаря Paganini вы за 1 минуту сможете сгенерировать отчет по еженедельной детализации продаж, и понять, из чего складывается сумма, приходящая на расчетный счет.\n\n'
    reply_text += 'Нажмите генерация отчета и бот по шагам проведет вас через создание магазина к генерации отчета\n\n'
    reply_text += 'Первые 4 генерации бесплатны!'
    await msg.answer(
        text=reply_text,
        reply_markup=get_main_kb()
    )


# ------------------ Onboarding Callbacks ------------------

@common_router.callback_query(F.data == 'onboarding_skip')
async def onboarding_skip(callback: types.CallbackQuery, state: FSMContext):
    """Skip onboarding and go to menu"""
    await state.clear()
    await callback.message.answer(
        text='☰ Меню\n\n💡 <i>Вы можете добавить магазин в любое время через меню</i>',
        reply_markup=get_menu_kb(),
        parse_mode='HTML'
    )
    await callback.answer()


@common_router.callback_query(F.data == 'onboarding_add_store')
async def onboarding_add_store(callback: types.CallbackQuery, state: FSMContext):
    """Start adding store from onboarding"""
    from handlers.reports import AddStore

    await state.update_data(from_onboarding=True)
    await state.set_state(AddStore.Name)
    await callback.message.answer('Введите название магазина:')
    await callback.answer()


@common_router.callback_query(F.data == 'onboarding_first_report')
async def onboarding_first_report(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    """Go to generate first report from onboarding"""
    from handlers.reports import handle_generate_report

    await state.clear()
    await handle_generate_report(callback.message, callback.from_user.id, session, state)
    await callback.answer()