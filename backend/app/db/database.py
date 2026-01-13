"""Database Configuration.

AsyncPG + SQLAlchemy setup for PostgreSQL with async support.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from ..core.config import settings
from ..core.constants import DatabaseLimits

database_url = settings.DATABASE_URL.replace(
    'postgresql://',
    'postgresql+asyncpg://'
)

engine = create_async_engine(
    database_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=DatabaseLimits.POOL_SIZE,
    max_overflow=DatabaseLimits.MAX_OVERFLOW
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()


async def get_db() -> AsyncSession:
    """Dependency to get database session.

    Yields:
        AsyncSession: Database session for the request

    Usage in FastAPI:
        @app.get("/items")
        async def read_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
