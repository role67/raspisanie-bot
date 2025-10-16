import os
from dotenv import load_dotenv
load_dotenv()  # Загружаем переменные окружения из .env

import asyncio
import logging
from contextlib import asynccontextmanager
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

from core import config, database
from core.database import get_session
from handlers import common, admin, schedule_handlers
from utils.scheduler import setup_scheduler

# Настройка логирования

class PrefixFormatter(logging.Formatter):
    PREFIXES = {
        'BOT': '[BOT]',
        'ERROR': '[ERROR]',
        'TELEGRAM': '[TELEGRAM]',
    }
    def format(self, record):
        prefix = ''
        if hasattr(record, 'prefix') and record.prefix in self.PREFIXES:
            prefix = self.PREFIXES[record.prefix] + ' '
        return f"{prefix}{super().format(record)}"

handler = logging.StreamHandler()
handler.setFormatter(PrefixFormatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s"))
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.handlers.clear()
logger.addHandler(handler)

# Путь для вебхука
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{config.WEBHOOK_URL}{WEBHOOK_PATH}"

# Инициализация бота и диспетчера
bot = Bot(token=config.BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

async def on_startup(bot_instance: Bot):
    """Действия при старте бота."""
    logger.info("Запуск бота...", extra={'prefix': 'BOT'})
    # Создание таблиц в БД
    try:
        async with database.engine.begin() as conn:
            await conn.run_sync(database.Base.metadata.create_all)
    except Exception as e:
        logger.error(f"Ошибка создания таблиц: {e}", extra={'prefix': 'ERROR'})
    
    # Установка вебхука
    try:
        await bot_instance.set_webhook(
            url=WEBHOOK_URL,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True
        )
        logger.info(f"Webhook установлен: {WEBHOOK_URL}", extra={'prefix': 'TELEGRAM'})
    except Exception as e:
        logger.error(f"Ошибка установки webhook: {e}", extra={'prefix': 'ERROR'})
    
    # Запуск планировщика
    try:
        setup_scheduler()
        logger.info("Планировщик запущен.", extra={'prefix': 'BOT'})
    except Exception as e:
        logger.error(f"Ошибка запуска планировщика: {e}", extra={'prefix': 'ERROR'})
    logger.info("Бот успешно запущен.", extra={'prefix': 'BOT'})

async def on_shutdown(bot_instance: Bot):
    """Действия при остановке бота."""
    logger.info("Остановка бота...", extra={'prefix': 'BOT'})
    try:
        await bot_instance.delete_webhook()
        logger.info("Webhook удалён.", extra={'prefix': 'TELEGRAM'})
    except Exception as e:
        logger.error(f"Ошибка удаления webhook: {e}", extra={'prefix': 'ERROR'})
    logger.info("Бот остановлен.", extra={'prefix': 'BOT'})


async def webhook_handle(request):
    """Обработчик входящих запросов от Telegram."""
    url = str(request.url)
    index = url.rfind('/')
    token = url[index+1:]
    if token != config.BOT_TOKEN:
        logger.error("Неверный токен в запросе webhook", extra={'prefix': 'ERROR'})
        return web.Response(status=403)
    try:
        update = types.Update.model_validate_json(await request.text())
        logger.info("Обновление получено от Telegram", extra={'prefix': 'TELEGRAM'})
        await dp.feed_update(bot=bot, update=update)
    except Exception as e:
        logger.error(f"Ошибка обработки webhook: {e}", extra={'prefix': 'ERROR'})
    return web.Response()

# Глобальное приложение для gunicorn
app = web.Application()
app.router.add_post(f"/{WEBHOOK_PATH}/{config.BOT_TOKEN}", webhook_handle)

def main():
    """Основная функция запуска."""
    logger.info("[SYSTEM] Запуск основной функции main()", extra={'prefix': 'BOT'})

    # Проверка конфигурации
    logger.info(f"[CONFIG] BOT_TOKEN: {config.BOT_TOKEN}", extra={'prefix': 'BOT'})
    logger.info(f"[CONFIG] DATABASE_URL: {config.DATABASE_URL}", extra={'prefix': 'BOT'})
    logger.info(f"[CONFIG] WEBHOOK_URL: {config.WEBHOOK_URL}", extra={'prefix': 'BOT'})
    logger.info(f"[CONFIG] PARSE_INTERVAL_MINUTES: {config.PARSE_INTERVAL_MINUTES}", extra={'prefix': 'BOT'})

    # Регистрация роутеров
    logger.info("[ROUTER] Регистрация роутера common", extra={'prefix': 'BOT'})
    dp.include_router(common.router)
    logger.info("[ROUTER] Регистрация роутера admin", extra={'prefix': 'BOT'})
    dp.include_router(admin.router)
    logger.info("[ROUTER] Регистрация роутера schedule_handlers", extra={'prefix': 'BOT'})
    dp.include_router(schedule_handlers.router)

    # Регистрация middleware для сессии БД
    logger.info("[MIDDLEWARE] Регистрация middleware для сессии БД", extra={'prefix': 'BOT'})
    dp.update.middleware(get_session)

    # Регистрация хуков startup/shutdown
    logger.info("[HOOK] Регистрация on_startup", extra={'prefix': 'BOT'})
    dp.startup.register(on_startup)
    logger.info("[HOOK] Регистрация on_shutdown", extra={'prefix': 'BOT'})
    dp.shutdown.register(on_shutdown)

    # Отключаем стандартный логгер aiohttp
    aiohttp_loggers = ["aiohttp.access", "aiohttp.server", "aiohttp.web", "aiohttp.websocket"]
    for name in aiohttp_loggers:
        logging.getLogger(name).setLevel(logging.WARNING)
    logger.info("[SYSTEM] Стандартные логи aiohttp отключены", extra={'prefix': 'BOT'})

    # Запуск без баннера
    logger.info("[SYSTEM] Запуск веб-сервера aiohttp", extra={'prefix': 'BOT'})
    web.run_app(app, host="0.0.0.0", port=8080, print=None)

if __name__ == "__main__":
    main()
