from aiogram import BaseMiddleware
from aiogram.types import Message
from typing import Callable, Awaitable, Dict, Any


class AllowPrivateMessagesOnly(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        # Разрешаем только сообщения в личке
        if isinstance(event, Message) and event.chat.type == "private":
            return await handler(event, data)

        # Все остальные апдейты игнорируются
        return
