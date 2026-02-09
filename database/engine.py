import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from database.models import Base

from services.logging import logger


# Don't log full DB_URL as it may contain credentials
db_url = os.getenv('DB_URL', '')
db_host = db_url.split('@')[-1].split('/')[0] if '@' in db_url else 'configured'
logger.info(f'Database host: {db_host}')

# Convert postgresql:// to postgresql+asyncpg:// for async driver
# Railway provides DB_URL with postgresql://, but we need asyncpg driver
if db_url.startswith('postgresql://'):
    db_url = db_url.replace('postgresql://', 'postgresql+asyncpg://', 1)
elif db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql+asyncpg://', 1)

engine = create_async_engine(
    db_url,
    echo=os.getenv('DB_ECHO', 'false').lower() == 'true'
)

session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def create_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def drop_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
