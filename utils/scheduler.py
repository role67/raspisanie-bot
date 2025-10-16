import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from core.config import PARSE_INTERVAL_MINUTES
from core.database import async_session
from utils.parser import parse_job

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def run_parsing():
    """Функция-обертка для запуска parse_job с сессией БД."""
    async with async_session() as session:
        await parse_job(session)

def setup_scheduler():
    """Настраивает и запускает планировщик задач."""
    try:
        # Добавляем одну задачу, которая сработает сразу и потом будет повторяться с интервалом.
        scheduler.add_job(
            run_parsing, 
            'interval', 
            minutes=PARSE_INTERVAL_MINUTES, 
            id='parse_schedule_job',
            next_run_time=None  # Указывает, что первый запуск должен быть немедленным
        )

        scheduler.start()
        logger.info(f"Планировщик запущен. Первый парсинг запущен немедленно, далее - каждые {PARSE_INTERVAL_MINUTES} минут.")
    except Exception as e:
        logger.error(f"Ошибка при запуске планировщика: {e}")
