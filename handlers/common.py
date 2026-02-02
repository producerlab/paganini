import os

from aiogram import Router, types, F
from aiogram.filters import Command, or_f, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy.ext.asyncio import AsyncSession

from keyboards.user_keyboards import get_menu_kb, get_subscribe_kb, get_contact_reply_kb, get_main_kb
from services import auth_service
from services.refs import orm_save_ref
from services.logging import logger

common_router = Router(name="common_router")

# Channel for subscription check (from .env)
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME', '@khosnullin_channel')


class Registration(StatesGroup):
    contact = State()


@common_router.message(Command("start"))
async def cmd_start(msg: types.Message, state: FSMContext, session: AsyncSession) -> None:
    """Command start"""
    await state.clear()


    reply_text = 'Paganini – маэстро по расшифровке финансовых отчетов (еженедельной детализации) для селлеров на Wildberries\n\n'
    reply_text += 'Этот бот создавался профессиональными селлерами на Amazon, Wildberries, OZON и других маркетплейсах, которые собаку съели на финансовых расшифровках WB\n\n'
    reply_text += 'Благодаря Paganini вы за 1 минуту сможете сгенерировать отчет по еженедельной детализации продаж, и понять, из чего складывается сумма, приходящая на расчетный счет.\n\n'
    reply_text += 'Нажмите генерация отчета и бот по шагам проведет вас через создание магазина к генерации отчета\n\n'
    reply_text += 'Первые 4 генерации бесплатны!'
    await msg.answer(text=reply_text)

    user_id = int(msg.from_user.id)
    is_registered = await auth_service.orm_check_user_reg(session, user_id)
    member = await msg.bot.get_chat_member(CHANNEL_USERNAME, user_id)

    if len(msg.text.split()) > 1:
        args = msg.text.split()[1]
        if args.startswith('ref_'):
            referrer_id = int(args.split('_')[1])
            logger.debug(f"Referral link used: referrer_id={referrer_id}")
            if referrer_id != msg.from_user.id:
                await orm_save_ref(session, referrer_id, msg.from_user.id)

    if is_registered:
        reply_text = f'Приветствую, {msg.from_user.first_name}!\n'
        reply_text += '☰ Меню:'
        await msg.answer(
            text=reply_text,
            reply_markup=get_menu_kb()
        )
    elif member.status not in ["member", "administrator", "creator"]:
        reply_text = f'Приветствую, {msg.from_user.first_name}!\n'
        reply_text += f'Для доступа к боту подпишитесь на канал {CHANNEL_USERNAME}, затем нажмите на кнопку "Проверить подписку". 👇'
        await msg.answer(
            text=reply_text,
            reply_markup=get_subscribe_kb()
        )
    else:
        await state.set_state(Registration.contact)
        await msg.answer(
            text="Пожалуйста, поделитесь своим контактом для регистрации в боте.\nДля этого нажмите на кнопку внизу. 👇",
            reply_markup=get_contact_reply_kb())


@common_router.callback_query(F.data == 'check_subscription')
async def check_subscription(callback: types.CallbackQuery, state: FSMContext):
    member = await callback.bot.get_chat_member(CHANNEL_USERNAME, callback.from_user.id)
    if member.status not in ["member", "administrator", "creator"]:
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
    await state.clear()
    try:
        await msg.bot.delete_message(chat_id=msg.chat.id, message_id=msg.message_id-1)
    except Exception:
        pass  # Ignore if message already deleted
    reply_text = '✅ Вы успешно зарегистрированы!\n'
    reply_text += 'Для перехода к управлению магазинами нажмите на кнопку – Управление магазинами 👇'

    await msg.answer(
        text=reply_text,
        reply_markup=get_menu_kb()
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