"""
Migration script: Convert tg_id columns from INTEGER to BIGINT

This is needed because Telegram user IDs can exceed the INTEGER limit (2,147,483,647).
Run this script once against the production database.

Usage:
    DATABASE_URL=postgresql://... python scripts/migrate_bigint.py
"""

import os
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# Convert postgres:// to postgresql+asyncpg://
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql+asyncpg://', 1)
elif DATABASE_URL.startswith('postgresql://'):
    DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://', 1)


async def migrate():
    engine = create_async_engine(DATABASE_URL, echo=True)

    async with engine.begin() as conn:
        # Drop foreign key constraints first
        print("Dropping foreign key constraints...")

        await conn.execute(text("""
            ALTER TABLE store DROP CONSTRAINT IF EXISTS store_tg_id_fkey;
        """))
        await conn.execute(text("""
            ALTER TABLE report DROP CONSTRAINT IF EXISTS report_tg_id_fkey;
        """))
        await conn.execute(text("""
            ALTER TABLE ref DROP CONSTRAINT IF EXISTS ref_referrer_id_fkey;
        """))
        await conn.execute(text("""
            ALTER TABLE payment DROP CONSTRAINT IF EXISTS payment_tg_id_fkey;
        """))

        # Alter column types
        print("Converting columns to BIGINT...")

        await conn.execute(text("""
            ALTER TABLE "user" ALTER COLUMN tg_id TYPE BIGINT;
        """))
        await conn.execute(text("""
            ALTER TABLE store ALTER COLUMN tg_id TYPE BIGINT;
        """))
        await conn.execute(text("""
            ALTER TABLE report ALTER COLUMN tg_id TYPE BIGINT;
        """))
        await conn.execute(text("""
            ALTER TABLE ref ALTER COLUMN referral_id TYPE BIGINT;
        """))
        await conn.execute(text("""
            ALTER TABLE ref ALTER COLUMN referrer_id TYPE BIGINT;
        """))
        await conn.execute(text("""
            ALTER TABLE payment ALTER COLUMN tg_id TYPE BIGINT;
        """))

        # Re-add foreign key constraints
        print("Re-adding foreign key constraints...")

        await conn.execute(text("""
            ALTER TABLE store ADD CONSTRAINT store_tg_id_fkey
            FOREIGN KEY (tg_id) REFERENCES "user"(tg_id);
        """))
        await conn.execute(text("""
            ALTER TABLE report ADD CONSTRAINT report_tg_id_fkey
            FOREIGN KEY (tg_id) REFERENCES "user"(tg_id);
        """))
        await conn.execute(text("""
            ALTER TABLE ref ADD CONSTRAINT ref_referrer_id_fkey
            FOREIGN KEY (referrer_id) REFERENCES "user"(tg_id);
        """))
        await conn.execute(text("""
            ALTER TABLE payment ADD CONSTRAINT payment_tg_id_fkey
            FOREIGN KEY (tg_id) REFERENCES "user"(tg_id);
        """))

        print("Migration completed successfully!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
