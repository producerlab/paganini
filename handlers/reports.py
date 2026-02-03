import os
from datetime import datetime
from aiogram import Router, types, F
from aiogram.filters import Command, or_f
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, FSInputFile, InputMediaPhoto
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from services.auth_service import orm_get_user
from services.logging import logger
from keyboards.user_keyboards import get_period_kb, get_main_kb, get_manage_kb, get_menu_kb, get_after_report_kb, \
    get_quarters_kb, get_quarter_period_kb, get_no_generations_kb, get_error_kb, get_onboarding_kb, get_confirm_report_kb, \
    get_store_edit_kb, get_delete_confirm_kb
from services.manage_stores import orm_add_store, orm_set_store, orm_edit_store, orm_check_store_owner, get_decrypted_token, \
    orm_edit_store_name, orm_edit_store_token, orm_delete_store, orm_get_store
from services.payment import orm_reduce_generations
from services.report_generator import generate_report_with_params, run_with_progress, orm_add_report, \
    InvalidTokenError, WBTimeoutError, NoDataError

reports_router = Router(name="reports_router")


# ------------------ Stores ------------------

class AddStore(StatesGroup):
    Name = State()
    Token = State()

media_folder = Path(os.getenv('MEDIA_ROOT')) / 'token'
media = [
    InputMediaPhoto(media=FSInputFile(media_folder / '1.jpg'), caption='Введите токен магазина, для этого в личном кабинете Wildberries следуйте по шагам на скриншотах'),
    InputMediaPhoto(media=FSInputFile(media_folder / '2.jpg')),
    InputMediaPhoto(media=FSInputFile(media_folder / '3.jpg')),
    InputMediaPhoto(media=FSInputFile(media_folder / '4.jpg')),
    InputMediaPhoto(media=FSInputFile(media_folder / '5.jpg'))
]

doc_number_instruction = Path(os.getenv('MEDIA_ROOT')) / 'doc_number' / 'instruction.jpg'


@reports_router.message(or_f(Command("manage_stores"), (F.text.lower().contains('управлен')), (F.text.lower().contains('магазин'))))
async def cmd_manage_stores(msg: types.Message, session: AsyncSession) -> None:
    """Command manage_stores"""
    await handle_manage_stores(msg, msg.from_user.id, session)


@reports_router.callback_query(F.data == 'cb_btn_manage_stores')
async def cb_manage_stores(callback: types.CallbackQuery, session: AsyncSession) -> None:
    """Callback manage_stores"""
    await handle_manage_stores(callback.message, callback.from_user.id, session)
    await callback.answer()


async def handle_manage_stores(msg: types.Message, tg_id, session: AsyncSession) -> None:
    from services.manage_stores import orm_get_user_stores
    stores = await orm_get_user_stores(session, tg_id)

    if not stores:
        reply_text = (
            '🏪 <b>У вас пока нет магазинов</b>\n\n'
            'Добавьте свой первый магазин WB, чтобы начать генерировать отчеты.\n\n'
            '<b>Что потребуется:</b>\n'
            '• Название магазина\n'
            '• API-токен из ЛК Wildberries\n\n'
            '💡 Токен можно создать в ЛК WB → Настройки → Доступ к API'
        )
    else:
        reply_text = '🏪 <b>Управление магазинами</b>'

    await msg.answer(
        text=reply_text,
        reply_markup=await get_manage_kb(session, tg_id),
        parse_mode='HTML'
    )

@reports_router.callback_query(F.data == 'cb_btn_add_store')
async def cb_add_store(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Callback add store"""
    reply_text = 'Введите название магазина:'
    await callback.message.answer(reply_text)
    await state.set_state(AddStore.Name)


@reports_router.message(AddStore.Name, F.text)
async def add_store_name(msg: types.Message, state: FSMContext):
    await state.update_data(tg_id=msg.from_user.id, name=msg.text)
    reply_text = 'Введите токен магазина Wildberries. При его создании необходимо выбрать доступ к следующим разделам:\n\n'
    reply_text += 'Контент, Статистика, Аналитика, Продвижение, Доступ чтение'
    await msg.answer_media_group(caption=reply_text, media=media)
    await state.set_state(AddStore.Token)


@reports_router.message(AddStore.Token, F.text)
async def add_store_token(msg: types.Message, state: FSMContext, session: AsyncSession):
    await state.update_data(token=msg.text)
    data = await state.get_data()
    await orm_add_store(session, data)

    from_onboarding = data.get('from_onboarding', False)

    if from_onboarding:
        # Continue onboarding flow
        reply_text = (
            '✅ <b>Магазин успешно добавлен!</b>\n\n'
            '<b>Шаг 2:</b> Создайте первый отчет\n'
            'Выберите период и получите детальную расшифровку финансов.\n\n'
            '💡 <i>Токен хранится в зашифрованном виде и используется только для получения данных из WB</i>'
        )
        await state.clear()
        await msg.answer(text=reply_text, reply_markup=get_onboarding_kb(2), parse_mode='HTML')
    else:
        reply_text = (
            '✅ <b>Магазин успешно добавлен!</b>\n\n'
            'Можете переходить к генерации отчета!\n\n'
            '💡 <i>Токен хранится в зашифрованном виде и используется только для получения данных из WB</i>'
        )
        await state.clear()
        await msg.answer(text=reply_text, reply_markup=get_menu_kb(), parse_mode='HTML')


@reports_router.callback_query(F.data.startswith('setstore_'))
async def cb_set_store(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    """Callback set store"""
    try:
        store_id = int(callback.data.split('_', 1)[1])
    except ValueError:
        await callback.answer("❌ Некорректный ID магазина", show_alert=True)
        return

    # Validate store ownership
    if not await orm_check_store_owner(session, store_id, callback.from_user.id):
        await callback.answer("❌ Магазин не найден или не принадлежит вам", show_alert=True)
        return

    await orm_set_store(session, callback.from_user.id, store_id)
    reply_text = f'Магазин выбран, можете переходить к генерации отчета'
    await callback.message.answer(reply_text)
    await callback.answer()

    await handle_generate_report(callback.message, callback.from_user.id, session, state)


class EditStore(StatesGroup):
    Name = State()
    Token = State()


@reports_router.callback_query(F.data.startswith('editstore_'))
async def cb_edit_store(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Callback edit store - show edit menu"""
    try:
        store_id = int(callback.data.split('_', 1)[1])
    except ValueError:
        await callback.answer("❌ Некорректный ID магазина", show_alert=True)
        return

    # Validate store ownership
    if not await orm_check_store_owner(session, store_id, callback.from_user.id):
        await callback.answer("❌ Магазин не найден или не принадлежит вам", show_alert=True)
        return

    store = await orm_get_store(session, store_id)
    await state.clear()

    reply_text = f'⚙️ <b>Настройки магазина "{store.name}"</b>\n\nВыберите действие:'
    await callback.message.answer(
        text=reply_text,
        reply_markup=get_store_edit_kb(store_id, store.name),
        parse_mode='HTML'
    )
    await callback.answer()


@reports_router.callback_query(F.data.startswith('edit_name_'))
async def cb_edit_store_name_start(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Start editing store name"""
    try:
        store_id = int(callback.data.split('_', 2)[2])
    except ValueError:
        await callback.answer("❌ Некорректный ID магазина", show_alert=True)
        return

    if not await orm_check_store_owner(session, store_id, callback.from_user.id):
        await callback.answer("❌ Магазин не найден", show_alert=True)
        return

    store = await orm_get_store(session, store_id)
    await state.update_data(store_id=store_id)
    await state.set_state(EditStore.Name)

    reply_text = f'Текущее название: <b>{store.name}</b>\n\nВведите новое название магазина:'
    await callback.message.answer(text=reply_text, parse_mode='HTML')
    await callback.answer()


@reports_router.message(EditStore.Name, F.text)
async def edit_store_name(msg: types.Message, state: FSMContext, session: AsyncSession):
    """Save new store name"""
    data = await state.get_data()
    store_id = data.get('store_id')

    await orm_edit_store_name(session, store_id, msg.text)
    await state.clear()

    reply_text = f'✅ Название магазина изменено на "<b>{msg.text}</b>"'
    await msg.answer(text=reply_text, reply_markup=get_menu_kb(), parse_mode='HTML')


@reports_router.callback_query(F.data.startswith('edit_token_'))
async def cb_edit_store_token_start(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Start editing store token"""
    try:
        store_id = int(callback.data.split('_', 2)[2])
    except ValueError:
        await callback.answer("❌ Некорректный ID магазина", show_alert=True)
        return

    if not await orm_check_store_owner(session, store_id, callback.from_user.id):
        await callback.answer("❌ Магазин не найден", show_alert=True)
        return

    await state.update_data(store_id=store_id)
    await state.set_state(EditStore.Token)

    reply_text = (
        '🔑 <b>Изменение токена</b>\n\n'
        'Введите новый токен магазина Wildberries.\n\n'
        'При создании токена выберите доступ к разделам:\n'
        '• Контент\n• Статистика\n• Аналитика\n• Продвижение'
    )
    await callback.message.answer_media_group(media=media)
    await callback.message.answer(text=reply_text, parse_mode='HTML')
    await callback.answer()


@reports_router.message(EditStore.Token, F.text)
async def edit_store_token(msg: types.Message, state: FSMContext, session: AsyncSession):
    """Save new store token"""
    data = await state.get_data()
    store_id = data.get('store_id')

    await orm_edit_store_token(session, store_id, msg.text)
    await state.clear()

    reply_text = '✅ Токен магазина успешно обновлен!'
    await msg.answer(text=reply_text, reply_markup=get_menu_kb())


@reports_router.callback_query(F.data.startswith('delete_store_'))
async def cb_delete_store_confirm(callback: types.CallbackQuery, session: AsyncSession) -> None:
    """Show delete confirmation"""
    try:
        store_id = int(callback.data.split('_', 2)[2])
    except ValueError:
        await callback.answer("❌ Некорректный ID магазина", show_alert=True)
        return

    if not await orm_check_store_owner(session, store_id, callback.from_user.id):
        await callback.answer("❌ Магазин не найден", show_alert=True)
        return

    store = await orm_get_store(session, store_id)

    reply_text = (
        f'🗑 <b>Удаление магазина "{store.name}"</b>\n\n'
        '⚠️ Это действие нельзя отменить.\n'
        'История отчетов сохранится.\n\n'
        'Вы уверены?'
    )
    await callback.message.answer(
        text=reply_text,
        reply_markup=get_delete_confirm_kb(store_id),
        parse_mode='HTML'
    )
    await callback.answer()


@reports_router.callback_query(F.data.startswith('confirm_delete_'))
async def cb_delete_store_execute(callback: types.CallbackQuery, session: AsyncSession) -> None:
    """Execute store deletion"""
    try:
        store_id = int(callback.data.split('_', 2)[2])
    except ValueError:
        await callback.answer("❌ Некорректный ID магазина", show_alert=True)
        return

    if not await orm_check_store_owner(session, store_id, callback.from_user.id):
        await callback.answer("❌ Магазин не найден", show_alert=True)
        return

    store = await orm_get_store(session, store_id)
    store_name = store.name

    await orm_delete_store(session, store_id, callback.from_user.id)

    reply_text = f'✅ Магазин "<b>{store_name}</b>" удален'
    await callback.message.answer(
        text=reply_text,
        reply_markup=get_menu_kb(),
        parse_mode='HTML'
    )
    await callback.answer()


# ------------------ Reports ------------------

class Report(StatesGroup):
    Period = State()
    Doc_num = State()
    Confirm = State()


@reports_router.message(or_f(Command("generate_report"), (F.text.lower().contains('отчет')), (F.text.lower().contains('отчёт'))))
async def cmd_generate_report(msg: types.Message, session: AsyncSession, state: FSMContext) -> None:
    """Command generate_report"""
    await handle_generate_report(msg, msg.from_user.id, session, state)


@reports_router.callback_query(F.data == 'cb_btn_generate_report')
async def cb_generate_report(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    """Callback generate_report"""
    await handle_generate_report(callback.message, callback.from_user.id, session, state)
    await callback.answer()


async def handle_generate_report(msg: types.Message, tg_id, session: AsyncSession, state: FSMContext) -> None:
    user = await orm_get_user(session, tg_id)
    if user.generations_left <= 0 and user.role not in {'admin', 'whitelist'}:
        reply_text = (
            f'📊 <b>{user.first_name}, генерации закончились</b>\n\n'
            f'Сделано отчетов: {user.generations_made}\n\n'
            'Пополните баланс или пригласите друзей для получения бонусов.'
        )
        await msg.answer(
            text=reply_text,
            reply_markup=get_no_generations_kb(),
            parse_mode='HTML'
        )
    elif user.selected_store_id:
        reply_text = (
            f'{user.first_name}, для генерации отчета у Вас выбран магазин "<b>{user.selected_store.name}</b>"\n'
            'Для изменения магазина перейдите в управление магазинами /manage_stores\n\n'
            f'📊 Осталось генераций: {user.generations_left}\n\n'
            'Чтобы создать отчет — выберите период за который его нужно сгенерировать 👇\n\n'
            '💡 <i>Данные за последнюю неделю появляются в WB с задержкой 2-3 дня</i>'
        )
        await msg.answer(
            text=reply_text,
            reply_markup=get_period_kb(),
            parse_mode='HTML'
        )
        await state.set_state(Report.Period)
        await state.update_data(
            token=get_decrypted_token(user.selected_store),
            name=user.selected_store.name,
            user_id=user.tg_id,
            store_id=user.selected_store.id,
        )
    else:
        reply_text = 'У вас не выбран магазин для генерации отчета\n'
        reply_text += 'Выберите текущий, или создайте новый'
        await msg.answer(
            text=reply_text
        )

        await handle_manage_stores(msg, tg_id, session)


@reports_router.callback_query(Report.Period, F.data == 'selectquarter')
async def cb_select_quarter(callback: CallbackQuery):
    """Показать список кварталов для выбора архивного периода"""
    reply_text = 'Пожалуйста, выберите интересующий вас квартал!'
    await callback.message.answer(
        text=reply_text,
        reply_markup=get_quarters_kb()
    )


@reports_router.callback_query(Report.Period, F.data.startswith('setquarter_'))
async def cb_select_quarter_weeks(callback: CallbackQuery):
    """Показать недели выбранного квартала"""
    quarter_data = callback.data.split('_', 1)[1]
    logger.debug(f"Selected quarter: {quarter_data}")
    reply_text = 'Чтобы создать отчет - выберите период за который его нужно сгенерировать. 👇'
    await callback.message.answer(
        text=reply_text,
        reply_markup=get_quarter_period_kb(quarter_data)
    )


@reports_router.callback_query(Report.Period, F.data.startswith('setweek_'))
async def cb_set_period(callback: CallbackQuery, state: FSMContext):
    period = callback.data.split('_', 1)[1]
    await state.update_data(period=period)
    caption = (
        '📄 <b>Введите номер документа из WB</b>\n\n'
        '<b>Где найти:</b>\n'
        '1️⃣ ЛК WB → Финансовые отчеты\n'
        '2️⃣ Колонка "Прочие удержания" → нажать на сумму\n'
        '3️⃣ Найти строку "ВБ.Продвижение"\n\n'
        '<b>Формат ввода:</b>\n'
        '• Один номер: <code>232411108</code>\n'
        '• Два номера: <code>232411108 233498006</code>\n'
        '• Если документа нет: введите <code>0</code>'
    )
    await callback.message.answer_photo(
        photo=FSInputFile(doc_number_instruction),
        caption=caption,
        parse_mode='HTML'
    )
    await state.set_state(Report.Doc_num)


@reports_router.message(Report.Doc_num, F.text)
async def cmd_set_doc_num(msg: types.Message, state: FSMContext):
    """Save doc number and show confirmation screen"""
    doc_num = msg.text
    await state.update_data(doc_num=doc_num)
    data = await state.get_data()

    # Show confirmation screen
    reply_text = (
        '📋 <b>Проверьте данные перед генерацией:</b>\n\n'
        f'🏪 Магазин: <b>{data["name"]}</b>\n'
        f'📅 Период: <b>{data["period"]}</b>\n'
        f'📄 Документ: <code>{data["doc_num"]}</code>\n\n'
        '❓ Всё верно?'
    )
    await msg.answer(
        text=reply_text,
        reply_markup=get_confirm_report_kb(),
        parse_mode='HTML'
    )
    await state.set_state(Report.Confirm)


@reports_router.callback_query(Report.Confirm, F.data == 'confirm_generate')
async def cb_confirm_generate(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Confirmed - start report generation"""
    data = await state.get_data()
    await state.clear()

    dates = data['period']
    doc_num = data['doc_num']
    store_name = data['name']
    store_token = data['token']
    tg_id = data['user_id']
    store_id = data['store_id']
    date = datetime.strptime(dates.split('-')[0], "%d.%m.%Y").date()

    msg = callback.message
    await callback.answer()

    try:
        progress_state = {}
        file_path = await run_with_progress(
            msg,
            "⏳ Формируется отчет, пожалуйста, подождите",
            generate_report_with_params,
            progress_state,
            dates, doc_num, store_token, store_name, tg_id, store_id
        )
        await msg.answer(
            text=(
                f'✅ <b>Отчет готов!</b>\n\n'
                f'🏪 Магазин: {store_name}\n'
                f'📅 Период: {dates}'
            ),
            parse_mode='HTML'
        )
        await msg.answer_document(
            FSInputFile(file_path),
            reply_markup=get_after_report_kb()
        )
        # Check if this is the first report for tip
        user = await orm_get_user(session, tg_id)
        is_first_report = user.generations_made == 0

        await orm_add_report(session, tg_id, date, file_path, store_id)
        await orm_reduce_generations(session, tg_id)

        if is_first_report:
            await msg.answer(
                text='💡 <i>Поздравляем с первым отчетом! Все ваши отчеты сохраняются и доступны для повторного скачивания.</i>',
                parse_mode='HTML'
            )
    except InvalidTokenError:
        logger.error(f"Invalid token for user {tg_id}")
        await msg.answer(
            text=(
                '❌ <b>Ошибка токена WB</b>\n\n'
                'Токен магазина неверный или не имеет нужных разрешений.\n\n'
                '<b>Что делать:</b>\n'
                '1. Пересоздайте токен в ЛК WB\n'
                '2. Убедитесь, что выбраны разрешения:\n'
                '   Контент, Статистика, Аналитика, Продвижение\n\n'
                '💡 Количество генераций осталось неизменным'
            ),
            reply_markup=get_error_kb('invalid_token'),
            parse_mode='HTML'
        )
    except WBTimeoutError:
        logger.error(f"WB API timeout for user {tg_id}")
        await msg.answer(
            text=(
                '❌ <b>Сервер WB не отвечает</b>\n\n'
                'API Wildberries слишком долго обрабатывает запрос.\n\n'
                '<b>Что делать:</b>\n'
                'Попробуйте повторить генерацию через 5-10 минут.\n\n'
                '💡 Количество генераций осталось неизменным'
            ),
            reply_markup=get_error_kb('timeout'),
            parse_mode='HTML'
        )
    except NoDataError:
        logger.error(f"No data for user {tg_id}, period {dates}")
        await msg.answer(
            text=(
                '❌ <b>Нет данных за выбранный период</b>\n\n'
                'WB API не вернул данные о продажах за указанную неделю.\n\n'
                '<b>Возможные причины:</b>\n'
                '• В этот период не было продаж\n'
                '• Данные еще не появились в WB (задержка 2-3 дня)\n\n'
                '💡 Попробуйте выбрать другой период'
            ),
            reply_markup=get_error_kb('no_data'),
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Report generation failed for user {tg_id}: {e}", exc_info=True)
        await msg.answer(
            text=(
                '❌ <b>Ошибка при формировании отчета</b>\n\n'
                'Произошла непредвиденная ошибка. Попробуйте позже или обратитесь в поддержку.\n\n'
                '💡 Количество генераций осталось неизменным'
            ),
            reply_markup=get_error_kb('timeout'),
            parse_mode='HTML'
        )
