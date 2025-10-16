from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from .config import DATABASE_URL

if not DATABASE_URL or not DATABASE_URL.startswith("postgresql+asyncpg://"):
    raise RuntimeError(
        f"DATABASE_URL не определена или имеет неверный формат: '{DATABASE_URL}'.\n"
        "Проверьте файл .env и убедитесь, что строка начинается с 'postgresql+asyncpg://...'"
    )

# SQLAlchemy base and engine setup
Base = declarative_base()
engine = create_async_engine(DATABASE_URL, echo=False, future=True)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_session(handler, event, data):
    async with async_session() as session:
        data["session"] = session
        return await handler(event, data)