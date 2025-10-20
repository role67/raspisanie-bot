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

        # Миграция старых записей расписания (если есть)
        async def migrate_old_schedule(conn):
            rows = await conn.fetch("SELECT id, subject, teacher, classroom, start_time, end_time, lesson_number FROM schedule")
            for row in rows:
                needs_update = not row['lesson_number'] or not row['start_time'] or not row['end_time']
                if needs_update:
                    import re
                    lesson_number = row['lesson_number'] or 1
                    m = re.search(r'(\d) ?пара', row['subject'] or '')
                    if m:
                        lesson_number = int(m.group(1))
                    from .parsers.lesson_times import WEEKDAY_TIMES
                    time_key = f"{lesson_number} пара"
                    time_range = WEEKDAY_TIMES.get(time_key, '')
                    if time_range and '-' in time_range:
                        start_time, end_time = [t.strip() for t in time_range.split('-')]
                    else:
                        start_time, end_time = '', ''
                    await conn.execute(
                        """
                        UPDATE schedule SET lesson_number = $1, start_time = $2, end_time = $3 WHERE id = $4
                        """,
                        lesson_number, start_time, end_time, row['id']
                    )
        
        async with pool.acquire() as conn:
            async with conn.transaction():
                await migrate_old_schedule(conn)
                await conn.execute("DELETE FROM schedule")
                await conn.execute("DELETE FROM replacements")
                # Вставляем новое расписание
                if schedule:
                    for group, days in schedule.items():
                        if isinstance(days, dict):
                            for day, lessons in days.items():
                                for lesson in lessons:
                                    await conn.execute(
                                        """
                                        INSERT INTO schedule (group_name, day_of_week, lesson_number, subject, teacher, classroom, start_time, end_time)
                                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                                        """,
                                        group,
                                        day,
                                        lesson.get('lesson_number'),
                                        lesson.get('subject'),
                                        lesson.get('teacher'),
                                        lesson.get('room'),
                                        lesson.get('start_time'),
                                        lesson.get('end_time')
                                    )
                        elif isinstance(days, list):
                            # Для практик
                            for lesson in days:
                                await conn.execute(
                                    """
                                    INSERT INTO schedule (group_name, day_of_week, lesson_number, subject, teacher, classroom, start_time, end_time)
                                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                                    """,
                                    group,
                                    lesson.get('day_of_week'),
                                    lesson.get('lesson_number'),
                                    lesson.get('subject'),
                                    lesson.get('teacher'),
                                    lesson.get('room'),
                                    lesson.get('start_time'),
                                    lesson.get('end_time')
                                )
                # Вставляем замены
                if replacements:
                    for group, dates in replacements.items():
                        for date, changes in dates.items():
                            for change in changes:
                                await conn.execute("""
                                    INSERT INTO replacements (date, group_name, lesson_number, new_subject, classroom)
                                    VALUES ($1, $2, $3, $4, $5)
                                """, date, group, change.get('lesson'), change.get('subject'), change.get('room'))
                await conn.execute("""
                    INSERT INTO schedule_updates (update_type)
                    VALUES ('schedule')
                """)
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
