from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_admin_reply_kb() -> ReplyKeyboardMarkup:
    """Get admin reply kb"""
    rkb = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text='User по Тел'),
                KeyboardButton(text='User по TG'),
            ],
            [
                KeyboardButton(text='Добавить платеж'),
                KeyboardButton(text='Последние платежи'),
            ],
            [
                KeyboardButton(text='Топ по генерациям'),
                KeyboardButton(text='Последние реги'),
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder='Введите команду'
    )

    return rkb