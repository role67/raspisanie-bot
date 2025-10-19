import os
import sys
import socket
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
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



from .db import create_tables
from .handlers import router as main_router
from .features import router as features_router
from .scheduler import setup_scheduler
from .admin import router as admin_router
from .middlewares import DbMiddleware
from .init_groups import init_groups
import asyncio

async def handle_webhook(request):
    try:
        data = await request.json()
        update = types.Update(**data)
        await request.app['dp'].feed_update(bot=request.app['bot'], update=update)
        return web.Response(text='ok')
    except Exception as e:
        logging.error(f"Error handling webhook: {e}")
        return web.Response(status=500)

async def on_startup(app):
    # Настраиваем вебхук
    webhook_url = os.getenv("WEBHOOK_URL", "https://raspisanie-bot-ozca.onrender.com")
    await app['bot'].set_webhook(f"{webhook_url}/webhook")
    logging.info(f"Webhook set to {webhook_url}/webhook")

async def on_shutdown(app):
    # Удаляем вебхук при выключении
    await app['bot'].delete_webhook()
    await app['bot'].session.close()

async def main():
    # Настраиваем логирование
    logging.basicConfig(level=logging.INFO)
    
    # Инициализируем бота
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    
    # Инициализируем диспетчер
    dp = Dispatcher()
    pool = await asyncpg.create_pool(DATABASE_URL)
    await create_tables(pool)
    
    # Инициализируем список групп
    await init_groups(pool)
    
    # Подключаем middleware для работы с базой данных
    dp.message.middleware(DbMiddleware(pool))
    dp.callback_query.middleware(DbMiddleware(pool))
    dp.include_router(main_router)
    dp.include_router(features_router)
    dp.include_router(admin_router)
    setup_scheduler()
    
    # Настраиваем веб-сервер
    app = web.Application()
    app['bot'] = bot
    app['dp'] = dp
    
    # Добавляем маршруты
    app.router.add_post("/webhook", handle_webhook)
    app.router.add_get("/", lambda r: web.Response(text="Bot is running!"))
    
    # Добавляем обработчики запуска/остановки
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    
    # Получаем порт из переменной окружения (Render использует PORT)
    port = int(os.getenv("PORT", 8080))
    
    print('Бот запущен')
    return app

if __name__ == "__main__":
    app = asyncio.run(main())
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
