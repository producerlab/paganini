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


async def on_startup(bot):

    run_param = False
    if run_param:
        await drop_db()

    await create_db()


async def on_shutdown(bot):
    logger.info("Bot is shutting down...")
    await close_http_clients()



async def main() -> None:
    """Entry point"""
    try:
        logging.info("Starting bot")
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)

        dp.update.middleware(DataBaseSession(session_pool=session_maker))
        dp.message.middleware(AllowPrivateMessagesOnly())

        await bot.delete_webhook(drop_pending_updates=True)
        await bot.set_my_commands(commands=user_commands, scope=types.BotCommandScopeAllPrivateChats())
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as ex:
        logger.error(f"Bot stopped with error: {ex}")
    finally:
        await bot.session.close()
        logger.info("Bot session closed")


if __name__ == "__main__":
    asyncio.run(main())