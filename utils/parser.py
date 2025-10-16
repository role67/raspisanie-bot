import asyncio
import hashlib
import logging
import re
from io import BytesIO
import pandas as pd
from docx import Document
import aiohttp
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from core.models import Schedule, Replacement, Group, FileHash
from core.config import MAIN_SCHEDULE_URL, REPLACEMENTS_URL

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Регулярные выражения
GROUP_PATTERN = re.compile(r'^[А-Яа-я]{2,4}-\d{2,3}$')
SUBJECT_TEACHER_ROOM_PATTERN = re.compile(r'(.+?)\s+([А-Я]\.[А-Я]\. [А-Яа-я]+|Пр\.работа|Лекция)\s*\(?([\w\d-]+|с/з|а/з|ДО)\)?')

async def fetch_file(session: aiohttp.ClientSession, url: str):
    """Асинхронно загружает файл."""
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.read()
    except aiohttp.ClientError as e:
        logger.error(f"Ошибка при загрузке файла {url}: {e}")
        return None

async def check_and_update_hash(db_session: AsyncSession, url: str, content: bytes):
    """Проверяет хеш файла и обновляет его, если он изменился."""
    new_hash = hashlib.sha256(content).hexdigest()
    
    result = await db_session.execute(select(FileHash).where(FileHash.file_url == url))
    file_hash_obj = result.scalar_one_or_none()

    if file_hash_obj and file_hash_obj.file_hash == new_hash:
        return False  # Хеш не изменился

    if file_hash_obj:
        file_hash_obj.file_hash = new_hash
    else:
        db_session.add(FileHash(file_url=url, file_hash=new_hash))
    
    await db_session.commit()
    return True # Хеш изменился

async def parse_schedule(db_session: AsyncSession, content: bytes):
    """Парсит XLS файл с основным расписанием."""
    logger.info("Начало парсинга основного расписания (XLS).")
    try:
        df = pd.read_excel(BytesIO(content), header=None)
        # Удаляем старое расписание
        await db_session.execute(delete(Schedule))
        
        all_groups = set()
        # Здесь должна быть сложная логика извлечения данных из структуры XLS.
        # Это упрощенный пример, который нужно адаптировать под реальный файл.
        # Предполагаем, что группы находятся в определенных строках/столбцах.
        
        # Примерный поиск групп
        for col in df.columns:
            for group_name in df[col].dropna():
                if isinstance(group_name, str) and GROUP_PATTERN.match(group_name.strip()):
                    all_groups.add(group_name.strip())

        logger.info(f"Найдено {len(all_groups)} групп в XLS.")
        
        # Обновление списка групп в БД
        result = await db_session.execute(select(Group.name))
        existing_groups = {row[0] for row in result}
        
        new_groups = all_groups - existing_groups
        if new_groups:
            db_session.add_all([Group(name=g) for g in new_groups])
        
        # ... Логика извлечения пар, предметов, преподавателей ...
        # Эта часть сильно зависит от структуры файла и требует детального анализа.
        
        await db_session.commit()
        logger.info("Парсинг основного расписания завершен.")
    except Exception as e:
        await db_session.rollback()
        logger.error(f"Ошибка при парсинге XLS: {e}", exc_info=True)

async def parse_replacements(db_session: AsyncSession, content: bytes):
    """Парсит DOCX файл с заменами."""
    logger.info("Начало парсинга замен (DOCX).")
    try:
        doc = Document(BytesIO(content))
        # Удаляем старые замены
        await db_session.execute(delete(Replacement))
        
        # ... Логика извлечения данных из DOCX ...
        # Требует адаптации под реальную структуру документа.
        # Пример:
        # current_date = None
        # for para in doc.paragraphs:
        #     text = para.text.strip()
        #     # Ищем дату, группу, номер пары и замену
        
        await db_session.commit()
        logger.info("Парсинг замен завершен.")
    except Exception as e:
        await db_session.rollback()
        logger.error(f"Ошибка при парсинге DOCX: {e}", exc_info=True)

async def parse_job(db_session: AsyncSession):
    """Основная задача парсинга, запускаемая планировщиком."""
    logger.info("Запуск задачи парсинга.")
    async with aiohttp.ClientSession() as session:
        # Парсинг основного расписания
        schedule_content = await fetch_file(session, MAIN_SCHEDULE_URL)
        if schedule_content and await check_and_update_hash(db_session, MAIN_SCHEDULE_URL, schedule_content):
            await parse_schedule(db_session, schedule_content)
        else:
            logger.info("Файл основного расписания не изменился.")

        # Парсинг замен
        replacements_content = await fetch_file(session, REPLACEMENTS_URL)
        if replacements_content and await check_and_update_hash(db_session, REPLACEMENTS_URL, replacements_content):
            await parse_replacements(db_session, replacements_content)
        else:
            logger.info("Файл замен не изменился.")
    logger.info("Задача парсинга завершена.")
