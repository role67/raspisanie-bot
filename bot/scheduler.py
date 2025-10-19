from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .parsers.schedule import fetch_schedule, fetch_replacements
import asyncio
import logging

__all__ = ['setup_scheduler']

async def update_data(pool):
    """Обновляет данные расписания и замен в БД"""
    try:
        schedule = fetch_schedule()
        replacements = fetch_replacements()
        
        async with pool.acquire() as conn:
            # Начинаем транзакцию
            async with conn.transaction():
                # Очищаем старые данные
                await conn.execute("DELETE FROM schedule")
                await conn.execute("DELETE FROM replacements")
                
                # Вставляем новое расписание
                if schedule:
                    for group, lessons in schedule.items():
                        for lesson in lessons:
                            await conn.execute("""
                                INSERT INTO schedule (group_name, lesson_number, subject, time)
                                VALUES ($1, $2, $3, $4)
                            """, group, lesson.get('lesson_number'), lesson.get('subject'), lesson.get('time'))
                
                # Вставляем замены
                if replacements:
                    for group, dates in replacements.items():
                        for date, changes in dates.items():
                            for change in changes:
                                await conn.execute("""
                                    INSERT INTO replacements (date, group_name, lesson_number, new_subject, classroom)
                                    VALUES ($1, $2, $3, $4, $5)
                                """, date, group, change.get('lesson'), change.get('subject'), change.get('room'))
        
        logging.info('Данные успешно обновлены')
    except Exception as e:
        logging.error(f'Ошибка при обновлении данных: {e}')

def setup_scheduler(app):
    """Настраивает планировщик обновления данных"""
    scheduler = AsyncIOScheduler()
    pool = app['db_pool']
    
    scheduler.add_job(
        update_data,
        'interval',
        minutes=20,
        args=[pool],
        id='update_schedule_job',
        replace_existing=True
    )
    
    scheduler.start()
    return scheduler
