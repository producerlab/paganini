"""
Скрипт миграции БД для добавления полей Модуль Банка.

Запуск:
    python scripts/migrate_modulbank.py

Для Railway:
    railway run python scripts/migrate_modulbank.py
"""

import asyncio
import os
import sys

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text
from database.engine import engine


async def migrate():
    """Добавление новых колонок для Модуль Банка."""

    async with engine.begin() as conn:
        # Проверяем, существуют ли уже колонки
        # Для PostgreSQL
        if 'postgresql' in str(engine.url):
            check_query = text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'payment'
                AND column_name IN ('modulbank_bill_id', 'modulbank_transaction_id')
            """)
            result = await conn.execute(check_query)
            existing_columns = [row[0] for row in result.fetchall()]

            if 'modulbank_bill_id' not in existing_columns:
                print("Добавляю колонку modulbank_bill_id...")
                await conn.execute(text(
                    "ALTER TABLE payment ADD COLUMN modulbank_bill_id VARCHAR(64)"
                ))
            else:
                print("Колонка modulbank_bill_id уже существует")

            if 'modulbank_transaction_id' not in existing_columns:
                print("Добавляю колонку modulbank_transaction_id...")
                await conn.execute(text(
                    "ALTER TABLE payment ADD COLUMN modulbank_transaction_id VARCHAR(64)"
                ))
            else:
                print("Колонка modulbank_transaction_id уже существует")

            # Делаем yoo_id nullable (если ещё не nullable)
            print("Делаю yoo_id nullable...")
            try:
                await conn.execute(text(
                    "ALTER TABLE payment ALTER COLUMN yoo_id DROP NOT NULL"
                ))
            except Exception as e:
                print(f"yoo_id уже nullable или ошибка: {e}")

        # Для SQLite
        elif 'sqlite' in str(engine.url):
            # SQLite не поддерживает ALTER COLUMN, но поддерживает ADD COLUMN
            try:
                await conn.execute(text(
                    "ALTER TABLE payment ADD COLUMN modulbank_bill_id VARCHAR(64)"
                ))
                print("Добавлена колонка modulbank_bill_id")
            except Exception as e:
                print(f"modulbank_bill_id: {e}")

            try:
                await conn.execute(text(
                    "ALTER TABLE payment ADD COLUMN modulbank_transaction_id VARCHAR(64)"
                ))
                print("Добавлена колонка modulbank_transaction_id")
            except Exception as e:
                print(f"modulbank_transaction_id: {e}")

        print("\n✅ Миграция завершена!")


if __name__ == "__main__":
    asyncio.run(migrate())
