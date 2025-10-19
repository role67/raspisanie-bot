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
        schedule_data = {}
        for col in df.columns[1:]:
            if str(col).strip() and str(col).strip() != 'nan':
                group_name = str(col).strip()
                schedule_data[group_name] = []
                for idx, row in df.iterrows():
                    time = str(row.iloc[0]).strip()
                    subject = str(row[col]).strip()
                    if subject and subject != 'nan':
                        schedule_data[group_name].append({
                            'time': time,
                            'subject': subject
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
if __name__ == "__main__":
    schedule = fetch_schedule()
    print(schedule.head())
    replacements = fetch_replacements()
    print(replacements)
    groups = extract_groups_from_schedule()
    print("Найденные группы:", groups)
