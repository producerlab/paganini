import asyncio
import os
import logging

from aiogram import Bot, Dispatcher, types

from dotenv import find_dotenv, load_dotenv

from middlewares.common import AllowPrivateMessagesOnly
from services.logging import logger

load_dotenv(find_dotenv())

from middlewares.db import DataBaseSession

from database.engine import create_db, drop_db, session_maker

from handlers.user import user_router
from handlers.reports import reports_router
from handlers.admin import admin_router
from handlers.partners import partners_router
from handlers.common import common_router

from common.bot_commands_list import user_commands
from services.report_generator import close_http_clients
from services.webhook_server import start_webhook_server, stop_webhook_server, set_payment_callback
from services.payment import process_modulbank_payment

# logging settings
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
)

# Init bot and Dispatcher
bot = Bot(token=os.getenv('TOKEN'))

# Load admin IDs from environment (comma-separated)
admin_ids_str = os.getenv('ADMIN_IDS', '')
bot.admins_list = [int(x.strip()) for x in admin_ids_str.split(',') if x.strip().isdigit()]

dp = Dispatcher()

# Register routers
dp.include_router(common_router)
dp.include_router(user_router)
dp.include_router(reports_router)
dp.include_router(admin_router)
dp.include_router(partners_router)

# Глобальная переменная для webhook runner
webhook_runner = None


async def on_startup(bot):
    global webhook_runner

    run_param = False
    if run_param:
        await drop_db()

    logger.info("Creating database tables...")
    await create_db()
    logger.info("Database tables created")

    # Запускаем webhook сервер для Модуль Банка
    # Railway использует переменную PORT, локально — WEBHOOK_PORT
    # Используем "or" чтобы пустая строка тоже заменялась на default
    webhook_host = os.getenv("WEBHOOK_HOST") or "0.0.0.0"
    webhook_port = int(os.getenv("PORT") or os.getenv("WEBHOOK_PORT") or "8080")

    logger.info(f"Starting webhook server on {webhook_host}:{webhook_port}...")

    # Устанавливаем callback для обработки платежей
    set_payment_callback(lambda data: process_modulbank_payment(data, bot, session_maker))

    webhook_runner = await start_webhook_server(webhook_host, webhook_port)
    logger.info("Webhook server started successfully")


async def on_shutdown(bot):
    global webhook_runner
    logger.info("Bot is shutting down...")

    # Останавливаем webhook сервер
    if webhook_runner:
        await stop_webhook_server(webhook_runner)

    await close_http_clients()



async def main() -> None:
    """Entry point"""
    try:
        logging.info("Starting bot")
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)

        dp.update.middleware(DataBaseSession(session_pool=session_maker))
        dp.message.middleware(AllowPrivateMessagesOnly())

        logger.info("Deleting webhook...")
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook deleted")

        logger.info("Setting bot commands...")
        await bot.set_my_commands(commands=user_commands, scope=types.BotCommandScopeAllPrivateChats())
        logger.info("Bot commands set")

        logger.info("Starting polling...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as ex:
        import traceback
        logger.error(f"Bot stopped with error: {ex}")
        logger.error(f"Traceback: {traceback.format_exc()}")
    finally:
        await bot.session.close()
        logger.info("Bot session closed")


if __name__ == "__main__":
    asyncio.run(main())