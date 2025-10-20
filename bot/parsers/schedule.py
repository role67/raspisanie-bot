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
    
    # Если список пуст, пробуем взять случайный агент из любой доступной платформы
    if not agents:
        all_agents = []
        for platform_agents in USER_AGENTS.values():
            all_agents.extend(platform_agents)
        user_agent = random.choice(all_agents) if all_agents else (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        )
    else:
        user_agent = random.choice(agents)
    
    return {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }


def process_subject_and_teacher(value):
    """Разделяет предмет и преподавателя из одной строки"""
    try:
        if not value or pd.isna(value) or str(value).strip().lower() == 'nan':
            return '', ''
    except Exception as e:
        print(f"Ошибка при проверке значения: {e}")
        return '', ''
    
    value = str(value).strip()
    parts = value.split(')')  # Разделяем по скобке, если есть
    
    # Если есть скобки (например: "МДК.04.01 (Болдовская)")
    if len(parts) > 1:
        subject = parts[0].strip() + ')'
        teacher = parts[1].strip()
        return subject, teacher
    
    # Если есть явное указание языка
    if '(нем)' in value.lower() or '(англ)' in value.lower():
        parts = value.split()
        subject_parts = []
        teacher_parts = []
        found_lang = False
        
        for part in parts:
            if '(нем)' in part.lower() or '(англ)' in part.lower():
                subject_parts.append(part)
                found_lang = True
            elif found_lang:
                teacher_parts.append(part)
            else:
                subject_parts.append(part)
                
        return ' '.join(subject_parts), ' '.join(teacher_parts)
    
    return value, ''

def process_teacher_and_room(value):
    """Разделяет учителя и кабинет из строки"""
    try:
        if not value or pd.isna(value) or str(value).strip().lower() == 'nan':
            return '', ''
    except Exception as e:
        print(f"Ошибка при проверке значения: {e}")
        return '', ''
        
    value = str(value).strip()
    
    # Специальная обработка общежития
    if value.lower() in ['общ', 'общ.', 'общага']:
        return '', 'Общежитие'
        
    # Если есть номер через дефис (например 201-4), это кабинет
    if '-' in value and any(c.isdigit() for c in value) and len(value) <= 7:
        return '', f"Каб. {value}"
        
    # Если это просто номер, это тоже кабинет
    if value.isdigit() and len(value) <= 4:
        return '', f"Каб. {value}"
    
    # Признаки преподавателя:
    # 1. Фамилия с инициалами (Иванов И.И.)
    if ' ' in value and any(c == '.' for c in value) and value.split()[0].istitle():
        return value, ''
    
    # 2. Просто фамилия с большой буквы
    if value.istitle() and value.isalpha() and len(value) > 3:
        return value, ''
        
    # 3. Фамилия с пробелами без точек (Иванова Мария)
    if ' ' in value and all(word.istitle() for word in value.split()) and value.replace(' ', '').isalpha():
        return value, ''
    
    # Иначе считаем что это не преподаватель и не кабинет
    return '', ''

def fetch_schedule():
    """Получает и парсит основное расписание"""
    try:
        try:
            headers = get_random_headers()
            resp = requests.get(SCHEDULE_URL, headers=headers)
            resp.raise_for_status()
            xls = BytesIO(resp.content)
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при получении файла расписания: {e}")
            return {}
        
        if not resp.content:
            print("Получен пустой файл расписания")
            return {}
            
        # Сохраняем хеш файла для отслеживания изменений
        file_hash = hash(resp.content)
        
        # По умолчанию начинаем с первой недели
        current_week = 1
        
        try:
            # Читаем файл с сохранением форматирования
            df = pd.read_excel(xls, engine='xlrd', na_values=[''])
            if df.empty:
                print("Файл расписания не содержит данных")
                return {}
        except pd.errors.EmptyDataError:
            print("Файл расписания пуст")
            return {}
        except pd.errors.ParserError as e:
            print(f"Ошибка парсинга файла Excel: {e}")
            return {}
        except Exception as e:
            print(f"Неожиданная ошибка при чтении Excel: {e}")
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
            df['Интервал'] = df['Интервал'].ffill()

        # Импортируем времена пар
        from .lesson_times import LESSON_TIMES, WEEKDAY_TIMES, SATURDAY_TIMES

        schedule_data = {}
        group_cols = [col for col in df.columns if '-' in str(col)]

        for group_col in group_cols:
            schedule_data[group_col] = {}

            if group_col in practice_data:
                schedule_data[group_col] = {'practice': [{'is_practice': True, 'practice_info': practice_data[group_col]}]}
                continue

            day_col = df.columns[0]
            current_day = None
            current_schedule = []
            lesson_counter = 0

            for idx, row in df.iterrows():
                if idx >= practice_start if len(practice_rows) > 0 else False:
                    break

                # Новый день недели
                if pd.notna(row[day_col]) and str(row[day_col]).strip():
                    if current_day and current_schedule:
                        if current_day not in schedule_data[group_col]:
                            schedule_data[group_col][current_day] = []
                        schedule_data[group_col][current_day].extend(current_schedule)
                    current_day = str(row[day_col]).strip()
                    current_schedule = []
                    lesson_counter = 0

                time = str(row.get('Интервал', '')).strip()
                current_value = str(row.get(group_col, '')).strip()
                next_col = df.columns[df.columns.get_loc(group_col) + 1]
                next_value = str(row.get(next_col, '')).strip()
                
                # Проверяем день недели
                if pd.notna(row[day_col]) and str(row[day_col]).strip():
                    # Обновляем текущий день и сохраняем предыдущий день
                    if current_day and current_schedule:
                        if current_day not in schedule_data[group_col]:
                            schedule_data[group_col][current_day] = []
                        schedule_data[group_col][current_day].extend(current_schedule)
                    current_day = str(row[day_col]).strip()
                    current_schedule = []
                    lesson_counter = 0
                    current_week = 1  # Сброс недели при новом дне

                # Проверяем разделение на недели
                # Разделительная линия определяется по пустому интервалу и наличию значения в колонке группы
                is_divider = pd.isna(row.get('Интервал')) and pd.notna(row.get(group_col))
                has_next_row = idx + 1 < len(df)
                
                if is_divider and has_next_row and current_day:  # Проверяем, что текущий день определен
                    next_row = df.iloc[idx + 1]
                    # Если следующая строка тоже содержит предмет, это разделение недель
                    if pd.notna(next_row.get(group_col)):
                        print(f"Найдено разделение недель для группы {group_col} в {current_day}")
                        current_week = 2  # Текущая пара относится ко второй неделе
                    continue
                
                # Пропускаем пустые строки и строки без времени
                if not time or (not current_value and not next_value) or current_value.lower() == 'nan':
                    continue

                # Определяем номер пары
                # Проверяем, что это действительно номер пары, а не заголовок
                if time and not any(x in time.lower() for x in ['снимаются', 'проводятся']):
                    lesson_counter += 1
                else:
                    continue
                
                # Логика определения предмета и преподавателя:
                subject = ''
                teacher = ''
                room = ''
                
                # Проверяем, есть ли в текущей строке и предмет и преподаватель
                subject, teacher_from_subject = process_subject_and_teacher(current_value)
                
                if teacher_from_subject:
                    teacher = teacher_from_subject
                    # Проверяем следующую ячейку на наличие кабинета
                    _, room = process_teacher_and_room(next_value)
                else:
                    # Если в строке только предмет, проверяем следующую на преподавателя
                    teacher_part, room_part = process_teacher_and_room(next_value)
                    if teacher_part:
                        teacher = teacher_part
                    if room_part:
                        room = room_part
                
                # Если текущее значение похоже на предмет (содержит точки, цифры или длинное)
                if any(c in current_value for c in ['.', '-']) or len(current_value.split()) > 1:
                    subject = current_value
                    # Следующее значение - преподаватель или кабинет
                    if next_value:
                        teacher_part, room_part = process_teacher_and_room(next_value)
                        teacher = teacher_part
                        room = room_part
                else:
                    # Текущее значение может быть преподавателем
                    teacher_part, room_part = process_teacher_and_room(current_value)
                    if teacher_part:  # Если это преподаватель
                        # Ищем предмет в предыдущей строке
                        if idx > 0:
                            prev_value = str(df.iloc[idx-1].get(group_col, '')).strip()
                            if prev_value and prev_value.lower() != 'nan':
                                subject = prev_value
                        teacher = teacher_part
                    else:  # Если это не преподаватель
                        subject = current_value
                    
                    # Проверяем следующее значение
                    if next_value:
                        next_teacher, next_room = process_teacher_and_room(next_value)
                        if next_teacher and not teacher:
                            teacher = next_teacher
                        if next_room and not room:
                            room = next_room

                # Определяем время начала и конца пары
                if current_day == 'Понедельник':
                    times_dict = LESSON_TIMES
                elif current_day == 'Суббота':
                    times_dict = SATURDAY_TIMES
                else:
                    times_dict = WEEKDAY_TIMES
                time_range = times_dict.get(time, '')
                if time_range and '-' in time_range:
                    start_time, end_time = [t.strip() for t in time_range.split('-')]
                else:
                    start_time, end_time = '', ''

                lesson_dict = {
                    'lesson_number': lesson_counter,
                    'time': time,
                    'subject': subject,
                    'teacher': teacher,
                    'room': room,
                    'start_time': start_time,
                    'end_time': end_time,
                    'week_number': current_week,
                    'is_practice': False,
                    'file_hash': file_hash
                }
                
                print(f"Добавлена пара для {group_col} ({day}, неделя {current_week}):")
                print(f"Предмет: {subject}")
                print(f"Преподаватель: {teacher}")
                print(f"Кабинет: {room}")
                print("---")
                current_schedule.append(lesson_dict)

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
        try:
            headers = get_random_headers()
            resp = requests.get(REPLACEMENTS_URL, headers=headers)
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при получении файла замен: {e}")
            return {}

        if not resp.content:
            print("Получен пустой файл замен")
            return {}
            
        try:
            doc = Document(BytesIO(resp.content))
        except Exception as e:
            print(f"Ошибка при открытии файла Word с заменами: {e}")
            return {}
        print(f"doc.tables: {len(doc.tables)} таблиц")
        replacements_data = {}
        current_date = None
        if not doc.tables:
            print("В документе не найдено таблиц с заменами")
            return {}
            
        for table_idx, table in enumerate(doc.tables):
            try:
                print(f"Обработка таблицы {table_idx}, строк: {len(table.rows)}")
                
                if not table.rows:
                    print(f"Таблица {table_idx} пуста")
                    continue
                    
                for row_idx, row in enumerate(table.rows):
                    try:
                        cells = [cell.text.strip() for cell in row.cells]
                        print(f"Row {row_idx}: {cells}")
                        
                        # Обработка даты
                        if len(cells) >= 1 and "20" in cells[0]:
                            current_date = cells[0]
                            print(f"Найдена дата: {current_date}")
                            continue
                            
                        if not current_date:
                            print(f"Пропуск строки {row_idx}: не определена дата")
                            continue
                            
                        if not any(cells):
                            continue
                            
                        if len(cells) >= 4:
                            group = cells[0].strip()
                            if group:
                                # Проверяем валидность данных
                                subject = cells[2].strip()
                                if not subject:
                                    print(f"Пропуск замены для группы {group}: не указан предмет")
                                    continue
                                    
                                if group not in replacements_data:
                                    replacements_data[group] = {}
                                if current_date not in replacements_data[group]:
                                    replacements_data[group][current_date] = []
                                    
                                replacement = {
                                    'lesson': cells[1].strip(),
                                    'subject': subject,
                                    'room': cells[3].strip(),
                                }
                                replacements_data[group][current_date].append(replacement)
                                print(f"Добавлена замена для группы {group}")
                                
                    except Exception as e:
                        print(f"Ошибка при обработке строки {row_idx}: {e}")
                        continue
                        
            except Exception as e:
                print(f"Ошибка при обработке таблицы {table_idx}: {e}")
                continue
                
        if not replacements_data:
            print("Не найдено данных о заменах")
        else:
            print("Найдены замены для групп:", list(replacements_data.keys()))
            
        return replacements_data
    except Exception as e:
        print(f"Ошибка при получении замен: {e}")
        return {}

def extract_groups_from_schedule():
    """Извлекает список групп из расписания"""
    try:
        schedule_data = fetch_schedule()
        if not schedule_data:
            print("Не удалось получить данные расписания")
            return []
            
        try:
            # Получаем список групп из ключей словаря
            groups = list(schedule_data.keys())
            if not groups:
                print("В расписании не найдено ни одной группы")
                return []
                
            # Фильтруем и очищаем названия групп
            cleaned_groups = []
            for group in groups:
                try:
                    group = str(group).strip()
                    if group and group not in ['Время', 'Дата', 'День', '']:
                        cleaned_groups.append(group)
                except (AttributeError, TypeError) as e:
                    print(f"Ошибка при обработке названия группы: {e}")
                    continue
                    
            if not cleaned_groups:
                print("После фильтрации не осталось групп")
                return []
                
            return sorted(list(set(cleaned_groups)))  # Убираем дубликаты и сортируем
            
        except Exception as e:
            print(f"Ошибка при обработке данных расписания: {e}")
            return []
            
    except Exception as e:
        print(f"Критическая ошибка при извлечении групп: {e}")
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
    
    Returns:
        str: Отформатированное расписание для отображения пользователю
    """
    try:
        if not isinstance(group_lessons, dict):
            print("Ошибка: group_lessons должен быть словарем")
            return "❌ Ошибка в формате данных расписания"
            
        if not day:
            print("Ошибка: не указан день недели")
            return "❌ Не указан день недели"
            
        # Валидация входных данных
        if replacements is not None and not isinstance(replacements, list):
            print("Ошибка: replacements должен быть списком")
            replacements = None
            
        if date_str and not isinstance(date_str, str):
            print("Предупреждение: date_str не является строкой")
            try:
                date_str = str(date_str)
            except:
                date_str = None
                
    except Exception as e:
        print(f"Ошибка при валидации входных данных: {e}")
        return "❌ Ошибка при обработке данных расписания"
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

    try:
        # Заголовок с датой
        if date_str:
            lines = [f"📅 {date_str} | {day_map.get(day, day)}\n"]
        else:
            lines = [f"📅 {day_map.get(day, day)}\n"]
            
        # Проверяем наличие расписания
        if not group_lessons or day not in group_lessons:
            lines.append("\n❌ Расписание на этот день не найдено")
            return '\n'.join(lines)

        lessons = group_lessons.get(day, [])
        if not isinstance(lessons, list):
            print(f"Ошибка: расписание на {day} не является списком")
            lines.append("\n❌ Ошибка в формате расписания")
            return '\n'.join(lines)
            
        # Обработка уроков
        for idx, lesson in enumerate(lessons, 1):
            try:
                if not isinstance(lesson, dict):
                    print(f"Ошибка: некорректный формат урока #{idx}")
                    continue
                    
                subject = lesson.get('subject', '').strip()
                teacher = lesson.get('teacher', '').strip()
                room = lesson.get('room', '').strip()
                time = lesson.get('time', '').strip()
                
                if not subject or subject == "-----":
                    continue
                    
            except Exception as e:
                print(f"Ошибка при обработке урока #{idx}: {e}")
                continue
                
    except Exception as e:
        print(f"Ошибка при форматировании расписания: {e}")
        return "❌ Ошибка при формировании расписания"
        # Время пары
        time_str = times_dict.get(time, time)
        # Формируем строку пары
        lesson_str = f"{idx}️⃣ {subject} | {time_str}"
        lines.append(lesson_str)
        
        if teacher:
            lines.append(f"👤 {teacher}")
        if room:
            lines.append(f"🚪 {room}")
        lines.append("")

    # Замены
    try:
        if replacements:
            if not isinstance(replacements, list):
                print("Ошибка: replacements должен быть списком")
                lines.append("❌ Ошибка при обработке замен")
            else:
                lines.append("🔄 Замены")
                for idx, rep in enumerate(replacements, 1):
                    try:
                        if not isinstance(rep, dict):
                            print(f"Ошибка: некорректный формат замены #{idx}")
                            continue
                            
                        rep_subject = rep.get('subject', '').strip()
                        rep_lesson = rep.get('lesson', '').strip()
                        rep_room = rep.get('room', '').strip()
                        rep_teacher = rep.get('teacher', '').strip()
                        
                        if not rep_subject or not rep_lesson:
                            print(f"Пропуск замены #{idx}: отсутствует предмет или номер урока")
                            continue
                            
                        # Формат: "История вместо Физики"
                        lines.append(f"📚 {rep_subject} вместо {rep_lesson}")
                        if rep_teacher:
                            lines.append(f"👤 {rep_teacher}")
                        if rep_room:
                            lines.append(f"🚪 Каб. {rep_room}")
                        lines.append("")
                        
                    except Exception as e:
                        print(f"Ошибка при обработке замены #{idx}: {e}")
                        continue
                        
    except Exception as e:
        print(f"Ошибка при обработке замен: {e}")
        lines.append("❌ Ошибка при обработке замен")

    # Время обновления
    try:
        if last_update:
            try:
                update_time = last_update.strftime('%d.%m.%Y %H:%M')
                lines.append(f"🕒 Обновлено: {update_time}")
            except Exception as e:
                print(f"Ошибка при форматировании времени обновления: {e}")
                lines.append("🕒 Время обновления недоступно")
    except Exception as e:
        print(f"Ошибка при добавлении времени обновления: {e}")

    try:
        return '\n'.join(lines)
    except Exception as e:
        print(f"Ошибка при формировании итогового текста: {e}")
        return "❌ Ошибка при формировании расписания"

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
