import asyncio
import os
import logging

from aiogram import Bot, Dispatcher, types

from dotenv import find_dotenv, load_dotenv

from middlewares.common import AllowPrivateMessagesOnly
from services.logging import logger

load_dotenv(find_dotenv())

from middlewares.db import DataBaseSession

from database.engine import create_db, drop_db, session_maker, engine
from sqlalchemy import text

from handlers.user import user_router
from handlers.reports import reports_router
from handlers.admin import admin_router
from handlers.partners import partners_router
from handlers.common import common_router

from common.bot_commands_list import user_commands
from services.report_generator import close_http_clients
from services.webhook_server import start_webhook_server, stop_webhook_server, set_payment_callback
from services.payment import process_modulbank_payment
from services.crypto import encrypt_token, is_token_encrypted

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


async def run_modulbank_migration():
    """Миграция для добавления колонок Модуль Банка (выполняется автоматически)."""
    async with engine.begin() as conn:
        # Проверяем тип БД и добавляем колонки если их нет
        if 'postgresql' in str(engine.url):
            # PostgreSQL
            check_query = text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'payment'
                AND column_name IN ('modulbank_bill_id', 'modulbank_transaction_id')
            """)
            result = await conn.execute(check_query)
            existing = [row[0] for row in result.fetchall()]

            if 'modulbank_bill_id' not in existing:
                logger.info("Миграция: добавляю колонку modulbank_bill_id...")
                await conn.execute(text("ALTER TABLE payment ADD COLUMN modulbank_bill_id VARCHAR(64)"))

            if 'modulbank_transaction_id' not in existing:
                logger.info("Миграция: добавляю колонку modulbank_transaction_id...")
                await conn.execute(text("ALTER TABLE payment ADD COLUMN modulbank_transaction_id VARCHAR(64)"))

            # Делаем yoo_id nullable
            try:
                await conn.execute(text("ALTER TABLE payment ALTER COLUMN yoo_id DROP NOT NULL"))
            except Exception:
                pass  # Уже nullable
        else:
            # SQLite
            try:
                await conn.execute(text("ALTER TABLE payment ADD COLUMN modulbank_bill_id VARCHAR(64)"))
                logger.info("Миграция: добавлена колонка modulbank_bill_id")
            except Exception:
                pass
            try:
                await conn.execute(text("ALTER TABLE payment ADD COLUMN modulbank_transaction_id VARCHAR(64)"))
                logger.info("Миграция: добавлена колонка modulbank_transaction_id")
            except Exception:
                pass


async def run_token_encryption_migration():
    """Миграция: шифрование plaintext токенов WB."""
    if not os.getenv('ENCRYPTION_KEY'):
        logger.warning("ENCRYPTION_KEY не установлен — токены не будут зашифрованы!")
        return

    from sqlalchemy import select, update
    from database.models import Store

    async with session_maker() as session:
        result = await session.execute(select(Store))
        stores = result.scalars().all()

        migrated = 0
        for store in stores:
            if not is_token_encrypted(store.token):
                encrypted = encrypt_token(store.token)
                await session.execute(
                    update(Store).where(Store.id == store.id).values(token=encrypted)
                )
                migrated += 1
                logger.info(f"Токен магазина #{store.id} зашифрован")

        if migrated > 0:
            await session.commit()
            logger.info(f"Миграция токенов завершена: зашифровано {migrated} токенов")


async def on_startup(bot):
    global webhook_runner

    run_param = False
    if run_param:
        await drop_db()

    logger.info("Creating database tables...")
    await create_db()
    logger.info("Database tables created")

    # Автоматическая миграция для Модуль Банка
    logger.info("Проверяю миграции...")
    await run_modulbank_migration()

    # Шифрование plaintext токенов
    logger.info("Проверяю шифрование токенов...")
    await run_token_encryption_migration()

    logger.info("Миграции завершены")

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