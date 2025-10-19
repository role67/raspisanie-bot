import pandas as pd
import requests
from io import BytesIO
from openpyxl import load_workbook
from docx import Document

SCHEDULE_URL = "https://www.nkptiu.ru/doc/raspisanie/raspisanie.xls"
REPLACEMENTS_URL = "https://www.nkptiu.ru/doc/raspisanie/zameni.docx"


def fetch_schedule():
    resp = requests.get(SCHEDULE_URL)
    resp.raise_for_status()
    xls = BytesIO(resp.content)
    # Для .xls используем pandas.read_excel, для .xlsx openpyxl
    df = pd.read_excel(xls, engine='openpyxl')
    return df


def fetch_replacements():
    resp = requests.get(REPLACEMENTS_URL)
    resp.raise_for_status()
    doc = Document(BytesIO(resp.content))
    data = []
    for table in doc.tables:
        for row in table.rows:
            data.append([cell.text for cell in row.cells])
    return data

def extract_groups_from_schedule():
    try:
        df = fetch_schedule()
        # Предполагаем, что группы находятся в заголовках столбцов
        groups = []
        for col in df.columns:
            # Очищаем названия групп от лишних пробелов и проверяем формат
            col = str(col).strip()
            # Здесь можно добавить валидацию формата группы
            if col and col not in ['Время', 'Дата', 'День', '']:
                groups.append(col)
        return sorted(list(set(groups)))  # Убираем дубликаты и сортируем
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
