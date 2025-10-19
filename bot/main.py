import os
import sys
import socket
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
import asyncpg

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMINS = [int(x) for x in os.getenv("ADMINS", "").split(",") if x]
DATABASE_URL = os.getenv("DATABASE_URL")

def is_bot_running():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('localhost', 8738))  # Используем специфический порт для проверки
        return False
    except socket.error:
        return True
    finally:
        sock.close()



from .db import create_tables
from .handlers import router as main_router
from .features import router as features_router
from .scheduler import setup_scheduler
from .admin import router as admin_router
from .middlewares import DbMiddleware
import asyncio

async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    # Удаляем webhook перед запуском бота
    await bot.delete_webhook(drop_pending_updates=True)
    
    dp = Dispatcher()
    pool = await asyncpg.create_pool(DATABASE_URL)
    await create_tables(pool)
    # Подключаем middleware для работы с базой данных
    dp.message.middleware(DbMiddleware(pool))
    dp.callback_query.middleware(DbMiddleware(pool))
    dp.include_router(main_router)
    dp.include_router(features_router)
    dp.include_router(admin_router)
    setup_scheduler()
    print('Бот запущен')
    await dp.start_polling(bot)

if __name__ == "__main__":
    if is_bot_running():
        print("Бот уже запущен!")
        sys.exit(1)
    asyncio.run(main())
