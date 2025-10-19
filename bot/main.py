import os
import sys
import socket
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
import asyncpg
from aiohttp import web
import logging

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



from .db import create_tables, update_groups_list
from .handlers import router as main_router
from .features import router as features_router
from .scheduler import setup_scheduler
from .admin import router as admin_router
from .middlewares import DbMiddleware
from .parsers.schedule import extract_groups_from_schedule
import asyncio

async def handle_index(request):
    return web.Response(text="Bot is running!")

async def main():
    # Настраиваем логирование
    logging.basicConfig(level=logging.INFO)
    
    # Инициализируем бота
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Инициализируем диспетчер
    dp = Dispatcher()
    pool = await asyncpg.create_pool(DATABASE_URL)
    await create_tables(pool)
    
    # Получаем и обновляем список групп
    groups = extract_groups_from_schedule()
    if groups:
        await update_groups_list(pool, groups)
        print(f"Обновлен список групп: {len(groups)} групп")
    else:
        print("Не удалось получить список групп")
    
    # Подключаем middleware для работы с базой данных
    dp.message.middleware(DbMiddleware(pool))
    dp.callback_query.middleware(DbMiddleware(pool))
    dp.include_router(main_router)
    dp.include_router(features_router)
    dp.include_router(admin_router)
    setup_scheduler()
    
    # Настраиваем веб-сервер
    app = web.Application()
    app.router.add_get("/", handle_index)
    
    # Запускаем бота и веб-сервер
    print('Бот запущен')
    
    # Получаем порт из переменной окружения (Render использует PORT)
    port = int(os.getenv("PORT", 8080))
    
    # Запускаем веб-сервер и бота параллельно
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    
    await asyncio.gather(
        site.start(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    if is_bot_running():
        print("Бот уже запущен!")
        sys.exit(1)
    asyncio.run(main())
