from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .parsers.schedule import fetch_schedule, fetch_replacements
import asyncio

scheduler = AsyncIOScheduler()

async def update_data():
    # Здесь будет логика обновления расписания и замен в БД
    schedule = fetch_schedule()
    replacements = fetch_replacements()
    # TODO: сохранить в БД
    print('Данные обновлены')


def setup_scheduler():
    scheduler.add_job(lambda: asyncio.create_task(update_data()), 'interval', minutes=20)
    scheduler.start()
