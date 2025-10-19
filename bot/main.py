import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
import asyncpg
from aiohttp import web
import logging
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMINS = [int(x) for x in os.getenv("ADMINS", "").split(",") if x]
DATABASE_URL = os.getenv("DATABASE_URL")



from .db import create_tables
from .handlers import router as main_router
from .features import router as features_router
from .scheduler import setup_scheduler
from .admin import router as admin_router
from .middlewares import DbMiddleware
from .init_groups import init_groups
import asyncio

WEBHOOK_PATH = "/webhook"
WEBAPP_HOST = "0.0.0.0"

async def on_startup(app: web.Application, webhook_url=None):
    bot = app['bot']
    if webhook_url is None:
        webhook_url = os.getenv("WEBHOOK_URL", "https://raspisanie-bot-ozca.onrender.com")
    
    webhook_secret = os.getenv("WEBHOOK_SECRET")
    await bot.set_webhook(
        url=f"{webhook_url}{WEBHOOK_PATH}",
        secret_token=webhook_secret
    )
    logging.info(f"Webhook установлен на {webhook_url}{WEBHOOK_PATH}")

async def on_shutdown(app: web.Application):
    bot = app['bot']
    # Close database pool first
    if 'db_pool' in app:
        try:
            pool = app['db_pool']
            await pool.expire_connections()
            await pool.close()
        except Exception as e:
            logging.error(f"Error closing database pool: {e}")
    
    # Then close bot session and webhook
    try:
        await bot.delete_webhook()
        await bot.session.close()
    except Exception as e:
        logging.error(f"Error closing bot session: {e}")

async def main():
    # Настраиваем логирование
    logging.basicConfig(level=logging.INFO)
    
    # Инициализируем бота и диспетчер
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()

    # Инициализируем базу данных с максимальным количеством соединений
    try:
        pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=30,  # Reduced timeout
            max_queries=50000,
            max_inactive_connection_lifetime=180.0,  # Reduced lifetime
            server_settings={
                'application_name': 'raspisanie_bot',
                'statement_timeout': '30000',  # 30 seconds
                'idle_in_transaction_session_timeout': '30000'  # 30 seconds
            }
        )
        # Сохраняем пул в объекте бота и приложении
        bot.db_pool = pool
        
        # Проверяем соединение
        async with pool.acquire() as conn:
            await conn.execute('SELECT 1')
            
        await create_tables(pool)
        await init_groups(pool)
        
        # Подключаем middleware и роутеры
        dp.message.middleware(DbMiddleware(pool))
        dp.callback_query.middleware(DbMiddleware(pool))
    except Exception as e:
        logging.error(f"Database initialization error: {e}")
        raise
    dp.include_router(main_router)
    dp.include_router(features_router)
    dp.include_router(admin_router)
    setup_scheduler()
    
    # Настраиваем вебхук
    app = web.Application()
    app['bot'] = bot
    app['db_pool'] = pool
    
    # Получаем и проверяем webhook_secret
    webhook_secret = os.getenv("WEBHOOK_SECRET")
    if not webhook_secret:
        logging.warning("WEBHOOK_SECRET не установлен!")
        webhook_secret = None
    
    # Настраиваем обработчик вебхука
    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=webhook_secret
    ).register(app, path=WEBHOOK_PATH)
    
    # Добавляем маршрут для проверки работоспособности
    app.router.add_get("/", lambda r: web.Response(text="Bot is running!"))
    
    # Добавляем обработчики запуска/остановки
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    
    print('Бот запущен')
    return app

if __name__ == "__main__":
    # Запускаем приложение
    app = asyncio.run(main())
    
    # Запускаем веб-сервер
    port = int(os.getenv("PORT", 8080))
    web.run_app(
        app,
        host="0.0.0.0",
        port=port,
        access_log=logging.getLogger("aiohttp.access")
    )
