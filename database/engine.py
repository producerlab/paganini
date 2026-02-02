import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from database.models import Base

from services.logging import logger


logger.info(f'Адрес DB {os.getenv("DB_URL")}')

engine = create_async_engine(
    os.getenv('DB_URL'),
    echo=os.getenv('DB_ECHO', 'false').lower() == 'true'
)

session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def create_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def drop_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
