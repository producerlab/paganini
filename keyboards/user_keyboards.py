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
    """Get menu kb"""
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📊 Генерация отчета', callback_data='cb_btn_generate_report'), InlineKeyboardButton(text='🏪 Управление магазинами', callback_data='cb_btn_manage_stores')],
        [InlineKeyboardButton(text='❓ Как пользоваться ботом', url='https://web.biznesnaamazon.ru/Paganini')],
        [InlineKeyboardButton(text='💎 Получить бонусные генерации', callback_data='cb_btn_bonus')],
        [InlineKeyboardButton(text='💡 Канал с лайфхаками', url='https://t.me/+TXjDiIu3hnJmYmZi'), InlineKeyboardButton(text='🛟 Поддержка', url='https://web.biznesnaamazon.ru/tlgrm?bot=paganini_support_bot')],
        [InlineKeyboardButton(text='👤 Профиль', callback_data='cb_btn_profile'), InlineKeyboardButton(text='🤝 Партнерка', callback_data='cb_btn_refs'), InlineKeyboardButton(text='💳 Оплата', callback_data='cb_btn_payment')],
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
    )

    return rkb


async def get_manage_kb(session, tg_id) -> InlineKeyboardMarkup:
    """Get manage stores kb"""
    ikb = InlineKeyboardBuilder()
    stores = await orm_get_user_stores(session=session, tg_id=tg_id)
    for store in stores:
        ikb.add(
            InlineKeyboardButton(text=f'Выбрать {store.name}', callback_data=f'setstore_{store.id}'),
            InlineKeyboardButton(text=f'Изменить {store.name}', callback_data=f'editstore_{store.id}'),
        )
    ikb.adjust(2)
    ikb.row(InlineKeyboardButton(text="➕ Добавить магазин", callback_data='cb_btn_add_store'), )

    return ikb.as_markup()


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
        [InlineKeyboardButton(text='📊 Генерация отчета', callback_data='cb_btn_generate_report')],
        [InlineKeyboardButton(text='☰ Меню', callback_data='cb_btn_menu')]
    ])

    return ikb


def get_payment_kb() -> InlineKeyboardMarkup:
    """Get payment kb"""
    ikb = InlineKeyboardBuilder()
    tariffs = {
        'one': {
            'name': 'Разовый',
            'price': 490.00,
            'generations_num': 1
        },
        'month': {
            'name': 'Месяц',
            'price': 1690.00,
            'generations_num': 4
        },'quarter': {
            'name': 'Квартал',
            'price': 4990.00,
            'generations_num': 12
        },'year': {
            'name': 'Год',
            'price': 17990.00,
            'generations_num': 52
        },
    }
    for tariff in tariffs.values():
        ikb.add(
            InlineKeyboardButton(
                text=f'Оплатить {tariff["name"]}',
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