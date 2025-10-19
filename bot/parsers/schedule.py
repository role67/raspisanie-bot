import pandas as pd
import requests
from io import BytesIO
from openpyxl import load_workbook
from docx import Document

SCHEDULE_URL = "https://www.nkptiu.ru/doc/raspisanie/raspisanie.xls"
REPLACEMENTS_URL = "https://www.nkptiu.ru/doc/raspisanie/zameni.docx"


def fetch_schedule():
    """Получает и парсит основное расписание"""
    try:
        resp = requests.get(SCHEDULE_URL)
        resp.raise_for_status()
        xls = BytesIO(resp.content)
        df = pd.read_excel(xls, engine='xlrd')
        
        # Очищаем и форматируем данные
        schedule_data = {}
        
        # Предполагаем, что первая строка - это заголовки с группами
        # Первый столбец обычно содержит время/номер пары
        for col in df.columns[1:]:  # Пропускаем первый столбец с временем
            if str(col).strip() and str(col).strip() != 'nan':
                group_name = str(col).strip()
                schedule_data[group_name] = []
                
                # Проходим по каждой строке для данной группы
                for idx, row in df.iterrows():
                    time = str(row.iloc[0]).strip()  # Время/номер пары
                    subject = str(row[col]).strip()  # Предмет для данной группы
                    
                    if subject and subject != 'nan':
                        schedule_data[group_name].append({
                            'time': time,
                            'subject': subject
                        })
        
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
        
        replacements_data = {}
        current_date = None
        
        for table in doc.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                
                # Проверяем, является ли первая ячейка датой
                if len(cells) >= 1 and "20" in cells[0]:  # Примерная проверка на дату
                    current_date = cells[0]
                    continue
                
                # Пропускаем пустые строки
                if not any(cells):
                    continue
                
                # Парсим данные замены
                if len(cells) >= 4:  # Минимум: группа, пара, предмет, кабинет
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
