"""
Webhook сервер для приёма уведомлений от Модуль Банка.

Запускается параллельно с Telegram ботом.
"""

import os
import logging
from typing import Optional, Callable, Awaitable

from aiohttp import web

from services.modulbank import verify_signature, parse_callback_data, get_secret_key
from services.logging import logger


# Callback для обработки успешных платежей
# Будет установлен из main.py
_payment_callback: Optional[Callable[[dict], Awaitable[None]]] = None


def set_payment_callback(callback: Callable[[dict], Awaitable[None]]):
    """
    Установка callback-функции для обработки успешных платежей.

    Args:
        callback: Async функция, принимающая данные платежа
    """
    global _payment_callback
    _payment_callback = callback


async def modulbank_webhook(request: web.Request) -> web.Response:
    """
    Обработчик webhook от Модуль Банка.

    Документация: https://sup.modulbank.ru/transaction_notifications

    Модуль Банк отправляет POST запрос с данными о платеже.
    Нужно ответить 200 OK, иначе будет 14 повторных попыток.
    """
    try:
        # Парсим данные из запроса
        data = await request.post()
        data_dict = dict(data)

        logger.info(f"Получен webhook от Модуль Банка: {data_dict.get('state')}, order_id: {data_dict.get('order_id')}")

        # Верифицируем подпись
        secret_key = get_secret_key()
        if not verify_signature(data_dict, secret_key):
            logger.warning(f"Невалидная подпись webhook: {data_dict}")
            # Всё равно возвращаем 200, чтобы не было повторных попыток
            return web.Response(status=200, text="Invalid signature")

        # Парсим данные
        payment_data = parse_callback_data(data_dict)

        if payment_data["is_success"]:
            logger.info(f"Успешный платёж: {payment_data['transaction_id']}, сумма: {payment_data['amount']}")

            # Вызываем callback для обработки платежа
            if _payment_callback:
                await _payment_callback(payment_data)
            else:
                logger.warning("Payment callback не установлен!")
        else:
            logger.warning(f"Неуспешный платёж: {payment_data.get('error_message')}")

        return web.Response(status=200, text="OK")

    except Exception as e:
        logger.error(f"Ошибка обработки webhook: {e}")
        # Возвращаем 200, чтобы Модуль Банк не повторял запросы
        return web.Response(status=200, text="Error processed")


async def health_check(request: web.Request) -> web.Response:
    """Health check endpoint."""
    return web.Response(status=200, text="OK")


def create_webhook_app() -> web.Application:
    """Создание aiohttp приложения для webhook."""
    app = web.Application()
    app.router.add_post('/webhook/modulbank', modulbank_webhook)
    app.router.add_get('/health', health_check)
    return app


async def start_webhook_server(host: str = "0.0.0.0", port: int = 8080) -> web.AppRunner:
    """
    Запуск webhook сервера.

    Args:
        host: Хост для прослушивания
        port: Порт для прослушивания

    Returns:
        AppRunner для последующей остановки
    """
    app = create_webhook_app()
    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, host, port)
    await site.start()

    logger.info(f"Webhook сервер запущен на {host}:{port}")
    return runner


async def stop_webhook_server(runner: web.AppRunner):
    """Остановка webhook сервера."""
    await runner.cleanup()
    logger.info("Webhook сервер остановлен")
