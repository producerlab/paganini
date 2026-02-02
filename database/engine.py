import os
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import Pool
from database.models import Base

from services.logging import logger


@event.listens_for(Pool, "connect")
def enable_foreign_keys(dbapi_connection, connection_record):
    dbapi_connection.execute("PRAGMA foreign_keys=ON")

logger.info(f'Адрес DB {os.getenv("DB_URL")}')

engine = create_async_engine(
    os.getenv('DB_URL'),
    connect_args={"check_same_thread": False},
    echo=os.getenv('DB_ECHO', 'false').lower() == 'true'
)

session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def create_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def drop_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)