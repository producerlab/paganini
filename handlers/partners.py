from aiogram import Router, types, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from keyboards.user_keyboards import get_bonus_kb
from services.auth_service import orm_get_user
from services.refs import generate_referral_link, orm_get_refs, orm_get_gens_for_bonus

partners_router = Router(name="partners_router")


@partners_router.callback_query(F.data == 'cb_btn_refs')
async def cb_refs(callback: types.CallbackQuery, session: AsyncSession) -> None:
    """Command refs"""
    user_id = int(callback.from_user.id)
    user = await orm_get_user(session, user_id)
    ref_link = await generate_referral_link(user_id)
    referrals = await orm_get_refs(session, user_id)
    reply_text = f'{callback.from_user.first_name}, ваша реферальная ссылка:\n'
    reply_text += f'{ref_link}\n\n'
    reply_text += f'💰 Заработано бонусов: {user.bonus_total} ₽\n'
    reply_text += f'💸 Доступно для использования: {user.bonus_left} ₽\n\n'
    reply_text += f'👥 Ваши рефералы:\n'
    for ref in referrals:
        reply_text += f'+{ref}\n'
    reply_text += '\n📌 За каждого пользователя, который оплатит доступ по вашей ссылке — вы получаете 10% от его платежа в виде бонусов. Эти бонусы можно тратить на покупку расшифровок финансовых отчётов прямо в боте.\n\n'
    reply_text += 'Рекомендуйте и зарабатывайте 🎯'
    await callback.answer()
    await callback.message.answer(
        text=reply_text,
        reply_markup=get_bonus_kb()
    )


@partners_router.callback_query(F.data.startswith('gensforbonus_'))
async def cb_pay_for(callback: CallbackQuery, session: AsyncSession):
    data = callback.data.split('_', 2)
    generations_num = int(data[1])
    amount = int(data[2])
    user = await orm_get_user(session, callback.from_user.id)
    bonus_left = user.bonus_left

    if bonus_left >= amount:
        await orm_get_gens_for_bonus(session, user.tg_id, amount, generations_num)
        reply_text = f'✅ Вам добавлено генераций: {generations_num}\n'
        reply_text += f'Осталось бонусов: {bonus_left - amount}'
    else:
        reply_text = '❌ У вас недостаточно бонусов:\n'
        reply_text += f'Осталось бонусов: {bonus_left}\n'
        reply_text += f'Необходимо для добавления генераций: {amount}'

    await callback.message.answer(
        text=reply_text,
        reply_markup=get_bonus_kb()
    )