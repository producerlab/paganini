from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.manage_stores import orm_get_user_stores
from services.report_generator import get_weeks_range, get_quarters_range, get_quarters_weeks


def get_main_kb() -> InlineKeyboardMarkup:
    """Get main kb"""
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='☰ Меню', callback_data='cb_btn_menu')]
    ])

    return ikb


def get_menu_kb() -> InlineKeyboardMarkup:
    """Get menu kb - simplified and clean"""
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📊 Создать отчёт', callback_data='cb_btn_generate_report')],
        [InlineKeyboardButton(text='🏪 Мои магазины', callback_data='cb_btn_manage_stores')],
        [InlineKeyboardButton(text='💎 Пополнить баланс', callback_data='cb_btn_payment')],
        [InlineKeyboardButton(text='💎 Получить бонусы', callback_data='cb_btn_bonus')],
        [InlineKeyboardButton(text='👤 Профиль', callback_data='cb_btn_profile'), InlineKeyboardButton(text='🤝 Партнёрка', callback_data='cb_btn_refs')],
        [InlineKeyboardButton(text='❓ Помощь', url='https://web.biznesnaamazon.ru/Paganini'), InlineKeyboardButton(text='🛟 Поддержка', url='https://web.biznesnaamazon.ru/tlgrm?bot=paganini_support_bot')],
    ])

    return ikb

def get_subscribe_kb() -> InlineKeyboardMarkup:
    """Get subscribe kb"""
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👉 Подписаться на канал", url=f"https://t.me/+TXjDiIu3hnJmYmZi")],
        [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_subscription")]
    ])

    return ikb


def get_contact_reply_kb() -> ReplyKeyboardMarkup:
    """Get contact reply kb"""
    rkb = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text='📲 Отправить свой номер', request_contact=True),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

    return rkb


async def get_manage_kb(session, tg_id) -> InlineKeyboardMarkup:
    """Get manage stores kb"""
    ikb = InlineKeyboardBuilder()
    stores = await orm_get_user_stores(session=session, tg_id=tg_id)
    for store in stores:
        ikb.add(
            InlineKeyboardButton(text=f'🏪 {store.name}', callback_data=f'setstore_{store.id}'),
            InlineKeyboardButton(text=f'✏️', callback_data=f'editstore_{store.id}'),
        )
    ikb.adjust(2)
    ikb.row(InlineKeyboardButton(text="➕ Добавить магазин", callback_data='cb_btn_add_store'), )

    return ikb.as_markup()


def get_store_edit_kb(store_id: int, store_name: str) -> InlineKeyboardMarkup:
    """Get store edit menu kb"""
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f'✏️ Изменить название', callback_data=f'edit_name_{store_id}')],
        [InlineKeyboardButton(text=f'🔑 Изменить токен', callback_data=f'edit_token_{store_id}')],
        [InlineKeyboardButton(text=f'🗑 Удалить магазин', callback_data=f'delete_store_{store_id}')],
        [InlineKeyboardButton(text='← Назад', callback_data='cb_btn_manage_stores')]
    ])
    return ikb


def get_delete_confirm_kb(store_id: int) -> InlineKeyboardMarkup:
    """Get delete confirmation kb"""
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='✅ Да, удалить', callback_data=f'confirm_delete_{store_id}')],
        [InlineKeyboardButton(text='❌ Отмена', callback_data=f'editstore_{store_id}')]
    ])
    return ikb


def get_after_store_edit_kb() -> InlineKeyboardMarkup:
    """Get kb shown after editing store (name/token)"""
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📊 Сгенерировать отчет', callback_data='cb_btn_generate_report')],
        [InlineKeyboardButton(text='🏪 Управление магазинами', callback_data='cb_btn_manage_stores')],
        [InlineKeyboardButton(text='☰ Меню', callback_data='cb_btn_menu')]
    ])
    return ikb


def get_period_kb() -> InlineKeyboardMarkup:
    """Get select period kb"""
    ikb = InlineKeyboardBuilder()
    weeks_range = get_weeks_range(6)
    for week in weeks_range:
        ikb.add(
            InlineKeyboardButton(text=f'{week}', callback_data=f'setweek_{week}'),
        )
    ikb.add(
        InlineKeyboardButton(text=f'📅 Выбрать более ранний период', callback_data=f'selectquarter'),
        InlineKeyboardButton(text='☰ Меню', callback_data='cb_btn_menu'),
    )
    ikb.adjust(1)

    return ikb.as_markup()


def get_quarters_kb() -> InlineKeyboardMarkup:
    """Get select quarter kb"""
    ikb = InlineKeyboardBuilder()
    quarters_range = get_quarters_range()
    for quarter in quarters_range:
        ikb.add(
            InlineKeyboardButton(text=f'{quarter[1]}', callback_data=f'setquarter_{quarter[0]}'),
        )
    ikb.add(
        InlineKeyboardButton(text='☰ Меню', callback_data='cb_btn_menu'),
    )
    ikb.adjust(1)

    return ikb.as_markup()


def get_quarter_period_kb(quarter_data: str) -> InlineKeyboardMarkup:
    """Get select from quarter period kb"""
    ikb = InlineKeyboardBuilder()
    quarter_data = quarter_data.split('_')
    year = int(quarter_data[0])
    quarter = int(quarter_data[1])
    weeks_range = get_quarters_weeks(year, quarter)
    for week in weeks_range:
        ikb.add(
            InlineKeyboardButton(text=f'{week}', callback_data=f'setweek_{week}'),
        )
    ikb.add(
        InlineKeyboardButton(text=f'📅 Выбрать другой квартал', callback_data=f'selectquarter'),
        InlineKeyboardButton(text='☰ Меню', callback_data='cb_btn_menu'),
    )
    ikb.adjust(1)

    return ikb.as_markup()


def get_after_report_kb() -> InlineKeyboardMarkup:
    """Get kb shown after generating report"""
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📊 Другой период', callback_data='cb_btn_generate_report')],
        [InlineKeyboardButton(text='🏪 Сменить магазин', callback_data='cb_btn_manage_stores')],
        [InlineKeyboardButton(text='☰ Меню', callback_data='cb_btn_menu')]
    ])

    return ikb


def get_payment_kb() -> InlineKeyboardMarkup:
    """Get payment kb with Year plan highlighted"""
    ikb = InlineKeyboardBuilder()
    tariffs = [
        {'name': 'Разовый', 'price': 490, 'generations_num': 1, 'highlight': False},
        {'name': 'Месяц', 'price': 1690, 'generations_num': 4, 'highlight': False},
        {'name': 'Квартал', 'price': 4990, 'generations_num': 12, 'highlight': False},
        {'name': 'Год', 'price': 17990, 'generations_num': 52, 'highlight': True},
    ]
    for tariff in tariffs:
        if tariff['highlight']:
            text = f'⭐️ Оплатить {tariff["name"]} — выгодно!'
        else:
            text = f'Оплатить {tariff["name"]}'
        ikb.add(
            InlineKeyboardButton(
                text=text,
                callback_data=f'payfor_{tariff["generations_num"]}_{tariff["price"]}'
            )
        )
    ikb.adjust(1)
    ikb.row(InlineKeyboardButton(text="☰ Меню", callback_data='cb_btn_menu'), )

    return ikb.as_markup()


def get_payment_check_kb(payment_id) -> InlineKeyboardMarkup:
    """Get kb for checking payment with input id"""
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='✅ Проверить оплату', callback_data=f'checkpayment_{payment_id}')],
        [InlineKeyboardButton(text="🔄 Выбрать другой тариф", callback_data="cb_btn_payment")]
    ])

    return ikb


def get_onboarding_kb(step: int) -> InlineKeyboardMarkup:
    """Get kb for onboarding step"""
    if step == 1:
        # Welcome - add store
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='🏪 Добавить магазин WB', callback_data='onboarding_add_store')],
            [InlineKeyboardButton(text='⏭ Пропустить', callback_data='onboarding_skip')]
        ])
    elif step == 2:
        # After store added - create first report
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='📊 Создать первый отчет', callback_data='onboarding_first_report')],
            [InlineKeyboardButton(text='☰ Перейти в меню', callback_data='cb_btn_menu')]
        ])
    else:
        # Fallback
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='☰ Меню', callback_data='cb_btn_menu')]
        ])


def get_error_kb(error_type: str) -> InlineKeyboardMarkup:
    """Get kb for specific error type with contextual actions"""
    buttons = []

    if error_type == 'invalid_token':
        buttons.append([InlineKeyboardButton(text='🏪 Проверить магазин', callback_data='cb_btn_manage_stores')])
    elif error_type == 'timeout':
        buttons.append([InlineKeyboardButton(text='🔄 Попробовать снова', callback_data='cb_btn_generate_report')])
    elif error_type == 'no_data':
        buttons.append([InlineKeyboardButton(text='📅 Выбрать другой период', callback_data='cb_btn_generate_report')])

    buttons.append([InlineKeyboardButton(text='🛟 Поддержка', url='https://web.biznesnaamazon.ru/tlgrm?bot=paganini_support_bot')])
    buttons.append([InlineKeyboardButton(text='☰ Меню', callback_data='cb_btn_menu')])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_no_generations_kb() -> InlineKeyboardMarkup:
    """Get kb when user has no generations left"""
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='💎 Пополнить', callback_data='cb_btn_payment')],
        [InlineKeyboardButton(text='🤝 Пригласить друзей', callback_data='cb_btn_refs')],
        [InlineKeyboardButton(text='☰ Меню', callback_data='cb_btn_menu')]
    ])

    return ikb


def get_confirm_report_kb() -> InlineKeyboardMarkup:
    """Get kb for confirming report generation"""
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='✅ Начать генерацию', callback_data='confirm_generate')],
        [InlineKeyboardButton(text='✏️ Изменить период', callback_data='cb_btn_generate_report')],
        [InlineKeyboardButton(text='☰ Меню', callback_data='cb_btn_menu')]
    ])

    return ikb


def get_bonus_kb() -> InlineKeyboardMarkup:
    """Get bonus kb"""
    ikb = InlineKeyboardBuilder()
    tariffs = {
        'bonus-1': {
            'name': '1 генерацию за бонусы',
            'price': 490,
            'generations_num': 1
        },
        'bonus-4': {
            'name': '4 генерации за бонусы',
            'price': 1690,
            'generations_num': 4
        },
    }
    for tariff in tariffs.values():
        ikb.add(
            InlineKeyboardButton(
                text=f'Получить {tariff["name"]}',
                callback_data=f'gensforbonus_{tariff["generations_num"]}_{tariff["price"]}'
            )
        )
    ikb.adjust(1)
    ikb.row(InlineKeyboardButton(text="☰ Меню", callback_data='cb_btn_menu'), )

    return ikb.as_markup()