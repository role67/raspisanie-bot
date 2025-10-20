import pandas as pd
import requests
from io import BytesIO
from docx import Document
import random
import os
from pathlib import Path

SCHEDULE_URL = "https://www.nkptiu.ru/doc/raspisanie/raspisanie.xls"
REPLACEMENTS_URL = "https://www.nkptiu.ru/doc/raspisanie/zameni.docx"

def load_user_agents():
    """Загружает User-Agent'ы из файлов"""
    agents = {
        'windows': [],
        'mac': [],
        'ios': [],
        'android': []
    }
    
    base_path = Path(__file__).parent.parent / 'useragents'
    
    # Загружаем по 100 агентов каждого типа
    for platform in agents.keys():
        file_path = base_path / f"{platform}.txt"
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                # Берем первые 100 строк, пропуская пустые
                agents[platform] = [line.strip() for line in f if line.strip()][:100]
    
    return agents

# Загружаем User-Agent'ы при импорте модуля
USER_AGENTS = load_user_agents()

def get_random_headers():
    """Возвращает случайный User-Agent и базовые заголовки"""
    # Выбираем платформу с разными весами
    platform = random.choices(
        ['windows', 'mac', 'ios', 'android'],
        weights=[0.4, 0.3, 0.2, 0.1]  # 40% Windows, 30% Mac, 20% iOS, 10% Android
    )[0]
    
    # Получаем список агентов для выбранной платформы
    agents = USER_AGENTS.get(platform, [])
    
    # Если список пуст, используем дефолтный User-Agent
    user_agent = random.choice(agents) if agents else (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    )
    
    return {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }


def fetch_schedule():
    """Получает и парсит основное расписание"""
    try:
        headers = get_random_headers()
        resp = requests.get(SCHEDULE_URL, headers=headers)
        resp.raise_for_status()
        xls = BytesIO(resp.content)
        try:
            df = pd.read_excel(xls, engine='xlrd')
        except Exception as e:
            print(f"Ошибка чтения xls: {e}")
            print(f"Размер файла: {len(resp.content)} байт")
            return {}
            
        # Проверяем есть ли строка "ПРАКТИКИ"
        practice_rows = df[df.iloc[:, 0] == "ПРАКТИКИ"].index
        practice_data = {}
        
        if len(practice_rows) > 0:
            practice_start = practice_rows[0]
            # Читаем практики после строки "ПРАКТИКИ"
            for idx, row in df.iloc[practice_start+1:].iterrows():
                if pd.notna(row[0]) and str(row[0]).strip():
                    group = str(row[0]).strip()
                    practice_info = str(row[2]).strip() if len(row) > 2 and pd.notna(row[2]) else ""
                    if group and practice_info and group != "ПРАКТИКИ":
                        practice_data[group] = practice_info
        
        print("df.head():", df.head())
        print("df.columns:", df.columns)
        
        # Заполняем пропуски времени (интервала)
        if 'Интервал' in df.columns:
            df['Интервал'] = df['Интервал'].fillna(method='ffill')
            
        schedule_data = {}
        # Группы идут через один столбец: [Группа, Unnamed, Группа, Unnamed, ...]
        group_cols = [col for col in df.columns if '-' in str(col)]
        
        for group_col in group_cols:
            schedule_data[group_col] = []
            
            # Проверяем, не на практике ли группа
            if group_col in practice_data:
                schedule_data[group_col] = [{'is_practice': True, 'practice_info': practice_data[group_col]}]
                continue
                
            # Получаем день недели из первой колонки
            day_col = df.columns[0]
            
            current_day = None
            current_schedule = []
            
            for idx, row in df.iterrows():
                if idx >= practice_start if len(practice_rows) > 0 else False:
                    break
                
                # Проверяем, не начался ли новый день
                if pd.notna(row[day_col]) and str(row[day_col]).strip():
                    if current_day and current_schedule:
                        if current_day not in schedule_data[group_col]:
                            schedule_data[group_col][current_day] = []
                        schedule_data[group_col][current_day].extend(current_schedule)
                    current_day = str(row[day_col]).strip()
                    current_schedule = []
                    
                time = str(row.get('Интервал', '')).strip()
                subject = str(row.get(group_col, '')).strip()
                
                # Получаем следующий столбец для преподавателя
                next_col = df.columns[df.columns.get_loc(group_col) + 1]
                teacher = str(row.get(next_col, '')).strip()
                
                # Пропускаем строки без времени или предмета
                if not time or not subject or subject.lower() == 'nan':
                    continue
                
                # Очищаем номер кабинета из строки преподавателя
                room = ''
                if teacher:
                    parts = teacher.split()
                    # Ищем часть, похожую на номер кабинета
                    for part in parts:
                        if any(c.isdigit() for c in part) and '-' in part:
                            room = part
                            # Удаляем номер кабинета из строки преподавателя
                            teacher = teacher.replace(room, '').strip()
                            break
                
                if subject and subject != "-----":
                    current_schedule.append({
                        'time': time,
                        'subject': subject,
                        'teacher': teacher if teacher and teacher.lower() != 'nan' else '',
                        'room': room,
                        'is_practice': False
                    })
            
            # Добавляем последний день
            if current_day and current_schedule:
                if not isinstance(schedule_data[group_col], dict):
                    schedule_data[group_col] = {}
                if current_day not in schedule_data[group_col]:
                    schedule_data[group_col][current_day] = []
                schedule_data[group_col][current_day].extend(current_schedule)
        print("schedule_data.keys():", list(schedule_data.keys()))
        return schedule_data
    except Exception as e:
        print(f"Ошибка при получении расписания: {e}")
        return {}

def fetch_replacements():
    """Получает и парсит замены в расписании"""
    try:
        headers = get_random_headers()
        resp = requests.get(REPLACEMENTS_URL, headers=headers)
        resp.raise_for_status()
        doc = Document(BytesIO(resp.content))
        print(f"doc.tables: {len(doc.tables)} таблиц")
        replacements_data = {}
        current_date = None
        for table_idx, table in enumerate(doc.tables):
            print(f"Таблица {table_idx}, строк: {len(table.rows)}")
            for row_idx, row in enumerate(table.rows):
                cells = [cell.text.strip() for cell in row.cells]
                print(f"Row {row_idx}: {cells}")
                if len(cells) >= 1 and "20" in cells[0]:
                    current_date = cells[0]
                    continue
                if not any(cells):
                    continue
                if len(cells) >= 4:
                    group = cells[0].strip()
                    if group:
                        if group not in replacements_data:
                            replacements_data[group] = {}
                        if current_date not in replacements_data[group]:
                            replacements_data[group][current_date] = []
                        replacement = {
                            'lesson': cells[1],
                            'subject': cells[2],
                            'room': cells[3]
                        }
                        replacements_data[group][current_date].append(replacement)
        print("replacements_data.keys():", list(replacements_data.keys()))
        return replacements_data
    except Exception as e:
        print(f"Ошибка при получении замен: {e}")
        return {}

def extract_groups_from_schedule():
    try:
        schedule_data = fetch_schedule()
        # Получаем список групп из ключей словаря
        groups = list(schedule_data.keys())
        # Фильтруем и очищаем названия групп
        cleaned_groups = []
        for group in groups:
            group = str(group).strip()
            if group and group not in ['Время', 'Дата', 'День', '']:
                cleaned_groups.append(group)
        return sorted(list(set(cleaned_groups)))  # Убираем дубликаты и сортируем
    except Exception as e:
        print(f"Ошибка при извлечении групп: {e}")
        return []

# Для теста:

def format_day_schedule(group_lessons, day, date_str=None, replacements=None, last_update=None):
    """
    Форматирует расписание для одного дня с заменами и временем обновления.
    group_lessons: словарь с расписанием по дням недели
    day: день недели ('Понедельник', ...)
    date_str: строка с датой в формате dd.mm.yyyy
    replacements: список замен для этого дня (если есть)
    last_update: datetime
    """
    from .lesson_times import LESSON_TIMES, WEEKDAY_TIMES, SATURDAY_TIMES
    from datetime import datetime

    day_map = {
        'Понедельник': 'Понедельник',
        'Вторник': 'Вторник',
        'Среда': 'Среда',
        'Четверг': 'Четверг',
        'Пятница': 'Пятница',
        'Суббота': 'Суббота'
    }

    # Определяем словарь времени
    if day == 'Понедельник':
        times_dict = LESSON_TIMES
    elif day == 'Суббота':
        times_dict = SATURDAY_TIMES
    else:
        times_dict = WEEKDAY_TIMES

    # Заголовок с датой
    if date_str:
        lines = [f"📅 {date_str} | {day_map.get(day, day)}\n"]
    else:
        lines = [f"📅 {day_map.get(day, day)}\n"]
        
    # Проверяем наличие расписания
    if not group_lessons or day not in group_lessons:
        lines.append("\n❌ Расписание на этот день не найдено")

    lessons = group_lessons.get(day, [])
    for idx, lesson in enumerate(lessons, 1):
        subject = lesson.get('subject', '').strip()
        teacher = lesson.get('teacher', '').strip()
        room = lesson.get('room', '').strip()
        time = lesson.get('time', '').strip()
        if not subject or subject == "-----":
            continue
        # Время пары
        time_str = times_dict.get(time, time)
        # Формат кабинета: "318-4" -> "Каб. 318-4"
        room_str = f"Каб. {room}" if room else ""
        # Вывод пары
        lines.append(f"{idx} {subject} | {time_str}")
        if teacher:
            lines.append(f"👤 {teacher}")
        if room_str:
            lines.append(f"🚪 {room_str}")
        lines.append("")

    # Замены
    if replacements:
        lines.append("🔄 Замены")
        for rep in replacements:
            rep_subject = rep.get('subject', '').strip()
            rep_lesson = rep.get('lesson', '').strip()
            rep_room = rep.get('room', '').strip()
            rep_teacher = rep.get('teacher', '').strip()
            # Формат: "История вместо Физики"
            lines.append(f"📚 {rep_subject} вместо {rep_lesson}")
            if rep_teacher:
                lines.append(f"👤 {rep_teacher}")
            if rep_room:
                lines.append(f"🚪 Каб. {rep_room}")
            lines.append("")

    # Время обновления
    if last_update:
        lines.append(f"� Обновлено: {last_update.strftime('%d.%m.%Y %H:%M')}")

    return '\n'.join(lines)

# Для теста:
if __name__ == "__main__":
    schedule = fetch_schedule()
    for group, lessons in schedule.items():
        print(f"\nРасписание для группы {group}:")
        for day in lessons:
            print(format_day_schedule(lessons, day))
    replacements = fetch_replacements()
    print(replacements)
    groups = extract_groups_from_schedule()
    print("Найденные группы:", groups)
