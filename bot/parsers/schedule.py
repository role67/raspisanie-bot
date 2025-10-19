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
            # Индекс преподавателя и кабинета
            subj_idx = df.columns.get_loc(group_col)
            teacher_idx = subj_idx + 1
            room_idx = subj_idx + 2
            for idx, row in df.iterrows():
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
                        'room': str(room).strip()
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
