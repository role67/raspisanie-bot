import pandas as pd
import requests
from io import BytesIO
from docx import Document

SCHEDULE_URL = "https://www.nkptiu.ru/doc/raspisanie/raspisanie.xls"
REPLACEMENTS_URL = "https://www.nkptiu.ru/doc/raspisanie/zameni.docx"


def fetch_schedule():
    """Получает и парсит основное расписание"""
    try:
        resp = requests.get(SCHEDULE_URL)
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
                
            # Индекс преподавателя и кабинета
            subj_idx = df.columns.get_loc(group_col)
            teacher_idx = subj_idx + 1
            room_idx = subj_idx + 2
            
            for idx, row in df.iterrows():
                if idx >= practice_start if len(practice_rows) > 0 else False:
                    break
                    
                lesson_number = idx + 1
                time = row.get('Интервал', '')
                subject = row.get(group_col, '')
                teacher = row.get(df.columns[teacher_idx], '') if teacher_idx < len(df.columns) else ''
                room = row.get(df.columns[room_idx], '') if room_idx < len(df.columns) else ''
                
                # Пропускаем пустые строки
                if pd.notna(subject) and str(subject).strip() and str(subject).strip().lower() != 'nan':
                    schedule_data[group_col].append({
                        'lesson_number': lesson_number,
                        'time': str(time).strip(),
                        'subject': str(subject).strip(),
                        'teacher': str(teacher).strip(),
                        'room': str(room).strip(),
                        'is_practice': False
                    })
        print("schedule_data.keys():", list(schedule_data.keys()))
        return schedule_data
    except Exception as e:
        print(f"Ошибка при получении расписания: {e}")
        return {}

def fetch_replacements():
    """Получает и парсит замены в расписании"""
    try:
        resp = requests.get(REPLACEMENTS_URL)
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

def format_schedule_for_group(group_lessons):
    """
    Форматирует расписание для группы в красивый текст для Telegram.
    group_lessons: список занятий (dict с ключами lesson_number, time, subject, teacher, room)
    """
    from .lesson_times import LESSON_TIMES, WEEKDAY_TIMES, SATURDAY_TIMES, get_schedule_string
    from datetime import datetime
    
    if not group_lessons:
        return "❌ Расписание не найдено."
        
    # Проверяем, не на практике ли группа
    if len(group_lessons) == 1 and group_lessons[0].get('is_practice', False):
        practice_info = group_lessons[0].get('practice_info', '')
        return f"⚡️ ГРУППА НА ПРАКТИКЕ ⚡️\n\n📝 {practice_info}"
        
    weekday = datetime.now().weekday()
    schedule_header = get_schedule_string(weekday)
    
    # Выбираем расписание времени в зависимости от дня недели
    if weekday == 0:  # Понедельник
        times_dict = LESSON_TIMES
    elif weekday == 5:  # Суббота
        times_dict = SATURDAY_TIMES
    else:  # Вторник-пятница
        times_dict = WEEKDAY_TIMES
    
    # Сгруппируем пары по номерам
    lessons_by_number = {}
    for lesson in group_lessons:
        time = lesson.get('time', '')
        if time not in lessons_by_number:
            lessons_by_number[time] = []
        lessons_by_number[time].append(lesson)
    
    lines = [schedule_header, "\n", "📅 РАСПИСАНИЕ ЗАНЯТИЙ\n"]
    
    for time, lessons in sorted(lessons_by_number.items()):
        if not time:
            continue
            
        lesson_num = time.split()[0]  # Получаем номер пары из "1 пара"
        lines.append(f"{'_' * 7} Занятие №{lesson_num} {'_' * 7}")
        lines.append(f"         ⏰«{times_dict.get(time, 'Время не указано')}»\n")
        
        for lesson in lessons:
            subject = lesson.get('subject', '').strip()
            teacher = lesson.get('teacher', '').strip()
            room = lesson.get('room', '').strip()
            
            if subject and subject != "-----":
                lines.append(f"📚 Предмет: {subject}")
                if teacher:
                    lines.append(f"👤 Преподаватель: {teacher}")
                if room:
                    lines.append(f"🚪 Кабинет: {room}")
                lines.append("")
        lines.append("")
    
    return '\n'.join(lines)

# Для теста:
if __name__ == "__main__":
    schedule = fetch_schedule()
    for group, lessons in schedule.items():
        print(f"\nРасписание для группы {group}:")
        print(format_schedule_for_group(lessons))
    replacements = fetch_replacements()
    print(replacements)
    groups = extract_groups_from_schedule()
    print("Найденные группы:", groups)
