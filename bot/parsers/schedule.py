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

# Для теста:
if __name__ == "__main__":
    schedule = fetch_schedule()
    print(schedule.head())
    replacements = fetch_replacements()
    print(replacements)
