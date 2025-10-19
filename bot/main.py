import os
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
import asyncpg
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

from bot.handlers import router as main_router
from bot.features import router as features_router
from bot.admin import router as admin_router
from bot.middlewares import DbMiddleware
from bot.init_groups import add_groups_to_db
from bot.scheduler import setup_scheduler

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
ADMINS = [int(admin_id) for admin_id in os.getenv("ADMINS", "").split(",")]
PORT = int(os.getenv("PORT", 8080))

async def create_pool():
    """Создает пул соединений с базой данных."""
    return await asyncpg.create_pool(
        dsn=DATABASE_URL,
        min_size=5,  # Увеличиваем минимальный размер пула
        max_size=20, # Увеличиваем максимальный размер пула
        command_timeout=30,
        max_queries=50000
    )

async def on_startup(bot: Bot, dp: Dispatcher, app: web.Application):
    """Действия при запуске бота."""
    await bot.set_webhook(f"{WEBHOOK_URL}/webhook", secret_token=WEBHOOK_SECRET)
    logging.info(f"Webhook установлен на {WEBHOOK_URL}/webhook")

    # Добавляем middleware
    pool = app['db_pool']
    dp.message.middleware(DbMiddleware(pool))
    dp.callback_query.middleware(DbMiddleware(pool))

async def on_shutdown(app: web.Application):
    """Действия при остановке бота."""
    logging.warning("Shutting down..")
    
    # Закрываем пул соединений
    if 'db_pool' in app:
        logging.info("Closing database pool...")
        await app['db_pool'].close()
        logging.info("Database pool closed.")
    
    logging.warning("Bye!")

async def create_tables(pool: asyncpg.Pool):
    """Создает таблицы в базе данных, если их нет."""
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                group_name VARCHAR(255)
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                name VARCHAR(255) PRIMARY KEY
            );
        """)

async def main():
    logging.basicConfig(level=logging.INFO)
    
    from aiogram.client.bot import DefaultBotProperties
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()

    # Регистрируем роутеры
    dp.include_router(main_router)
    dp.include_router(features_router)
    dp.include_router(admin_router)

    app = web.Application()
    app['db_pool'] = await create_pool()
    app['bot'] = bot  # Store bot instance in app

    # Создаем таблицы
    await create_tables(app['db_pool'])
    
    # Добавляем группы в базу данных
    groups_added = await add_groups_to_db(app['db_pool'])
    logging.info(f"Добавлено {groups_added} групп в базу данных")

    # Настраиваем apscheduler
    scheduler = AsyncIOScheduler()
    setup_scheduler(scheduler, bot, app['db_pool'])
    
    # Configure webhook
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_requests_handler.register(app, path="/webhook")

    # Startup and shutdown hooks
    app.on_startup.append(lambda app: on_startup(bot, dp, app))
    app.on_shutdown.append(on_shutdown)

    # Store bot and dispatcher instances in app
    app['bot'] = bot
    app['dp'] = dp

    # Setup AIOHTTP app
    setup_application(app, dp, bot=bot)

    # Run application
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    logging.info("Бот запущен")
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
