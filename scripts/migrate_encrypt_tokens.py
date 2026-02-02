#!/usr/bin/env python3
"""
Migration script to encrypt existing plaintext tokens in the database.
Run this ONCE after deploying the encryption feature.

Usage:
    python scripts/migrate_encrypt_tokens.py

Prerequisites:
    1. Set ENCRYPTION_KEY in environment
    2. Set DB_URL in environment
"""
import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from database.models import Store
from services.crypto import encrypt_token, is_token_encrypted, generate_encryption_key


async def migrate_tokens():
    """Encrypt all plaintext tokens in the database."""

    # Check if encryption key is set
    encryption_key = os.getenv('ENCRYPTION_KEY')
    if not encryption_key:
        print("ERROR: ENCRYPTION_KEY is not set!")
        print("\nGenerate a key with:")
        print(f"  ENCRYPTION_KEY={generate_encryption_key()}")
        print("\nAdd this to your .env file, then run this script again.")
        return False

    # Connect to database
    db_url = os.getenv('DB_URL')
    if not db_url:
        print("ERROR: DB_URL is not set!")
        return False

    engine = create_async_engine(db_url)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Get all stores
        result = await session.execute(select(Store))
        stores = result.scalars().all()

        migrated = 0
        skipped = 0
        errors = 0

        print(f"Found {len(stores)} stores to check...")

        for store in stores:
            try:
                if is_token_encrypted(store.token):
                    print(f"  Store {store.id} ({store.name}): already encrypted, skipping")
                    skipped += 1
                    continue

                # Encrypt the token
                encrypted = encrypt_token(store.token)

                # Update in database
                await session.execute(
                    update(Store)
                    .where(Store.id == store.id)
                    .values(token=encrypted)
                )

                print(f"  Store {store.id} ({store.name}): encrypted successfully")
                migrated += 1

            except Exception as e:
                print(f"  Store {store.id} ({store.name}): ERROR - {e}")
                errors += 1

        # Commit all changes
        await session.commit()

        print(f"\n=== Migration Complete ===")
        print(f"  Migrated: {migrated}")
        print(f"  Skipped (already encrypted): {skipped}")
        print(f"  Errors: {errors}")

        return errors == 0


if __name__ == '__main__':
    print("=== Token Encryption Migration ===\n")
    success = asyncio.run(migrate_tokens())
    sys.exit(0 if success else 1)
