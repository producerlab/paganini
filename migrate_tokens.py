"""
Миграция: шифрование существующих plaintext токенов WB.

Запуск: python migrate_tokens.py

Этот скрипт:
1. Находит все магазины с незашифрованными токенами
2. Шифрует их с помощью ENCRYPTION_KEY
3. Обновляет в базе данных

Безопасно запускать повторно — уже зашифрованные токены пропускаются.
"""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import select, update
from database.engine import engine, session_maker
from database.models import Store
from services.crypto import encrypt_token, is_token_encrypted
from services.logging import logger


async def migrate_tokens():
    """Шифрование всех plaintext токенов."""

    # Проверяем что ENCRYPTION_KEY установлен
    if not os.getenv('ENCRYPTION_KEY'):
        print("❌ ENCRYPTION_KEY не установлен!")
        print("Установите переменную окружения ENCRYPTION_KEY перед запуском миграции.")
        return

    async with session_maker() as session:
        # Получаем все магазины
        result = await session.execute(select(Store))
        stores = result.scalars().all()

        migrated = 0
        skipped = 0

        for store in stores:
            if is_token_encrypted(store.token):
                # Уже зашифрован
                skipped += 1
                logger.info(f"Магазин #{store.id} '{store.name}' — токен уже зашифрован, пропускаю")
            else:
                # Шифруем
                encrypted = encrypt_token(store.token)
                await session.execute(
                    update(Store)
                    .where(Store.id == store.id)
                    .values(token=encrypted)
                )
                migrated += 1
                logger.info(f"Магазин #{store.id} '{store.name}' — токен зашифрован ✓")

        await session.commit()

        print(f"\n{'='*50}")
        print(f"Миграция завершена!")
        print(f"  Зашифровано: {migrated}")
        print(f"  Пропущено (уже зашифрованы): {skipped}")
        print(f"{'='*50}")


if __name__ == "__main__":
    asyncio.run(migrate_tokens())
