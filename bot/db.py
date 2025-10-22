
GROUPS_TABLE = """
CREATE TABLE IF NOT EXISTS groups (
    name TEXT PRIMARY KEY,
    updated_at TIMESTAMP DEFAULT NOW()
);
"""

USER_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    group_name TEXT REFERENCES groups(name),
    joined_at TIMESTAMP DEFAULT NOW(),
    role TEXT DEFAULT NULL -- роль: 'student', 'teacher', NULL
);
"""

SUBJECTS_TABLE = """
CREATE TABLE IF NOT EXISTS subjects (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE,
    short_name TEXT
);
"""

TEACHERS_TABLE = """
CREATE TABLE IF NOT EXISTS teachers (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE
);
"""

SCHEDULE_TABLE = """
CREATE TABLE IF NOT EXISTS schedule (
    id SERIAL PRIMARY KEY,
    group_name TEXT,
    day_of_week TEXT,
    lesson_number INT,
    subject_id INT REFERENCES subjects(id),
    teacher_id INT REFERENCES teachers(id),
    classroom TEXT,
    start_time TIME,
    end_time TIME,
    week_number INT NOT NULL, -- 1 или 2 для разных недель
    has_two_week_schedule BOOLEAN DEFAULT FALSE, -- флаг, указывающий что у группы есть разное расписание по неделям
    file_hash TEXT -- для отслеживания изменений файла
);
"""

CURRENT_WEEK_TABLE = """
CREATE TABLE IF NOT EXISTS current_week (
    id INT PRIMARY KEY DEFAULT 1,
    week_number INT NOT NULL, -- 1 или 2
    changed_at TIMESTAMP DEFAULT NOW()
);
"""

REPLACEMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS replacements (
    id SERIAL PRIMARY KEY,
    date DATE,
    group_name TEXT,
    lesson_number INT,
    old_subject TEXT,
    new_subject TEXT,
    teacher TEXT,
    classroom TEXT
);
"""

SCHEDULE_UPDATES_TABLE = """
CREATE TABLE IF NOT EXISTS schedule_updates (
    id SERIAL PRIMARY KEY,
    updated_at TIMESTAMP DEFAULT NOW(),
    update_type TEXT
);
"""

async def create_tables(pool):
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Сохраняем текущие группы перед удалением
            existing_groups = await conn.fetch("SELECT name FROM groups")
            existing_groups = [g['name'] for g in existing_groups]
            
            # Сохраняем текущую неделю
            current_week = await conn.fetchval(
                "SELECT week_number FROM current_week WHERE id = 1"
            ) or 2
            
            # Удаляем старые таблицы для чистой установки
            await conn.execute("""
                DROP TABLE IF EXISTS schedule CASCADE;
                DROP TABLE IF EXISTS subjects CASCADE;
                DROP TABLE IF EXISTS teachers CASCADE;
                DROP TABLE IF EXISTS current_week CASCADE;
            """)
            
            # Создаем основные таблицы
            await conn.execute(GROUPS_TABLE)
            await conn.execute(USER_TABLE)
            await conn.execute(SUBJECTS_TABLE)
            await conn.execute(TEACHERS_TABLE)
            await conn.execute(SCHEDULE_TABLE)
            await conn.execute(REPLACEMENTS_TABLE)
            await conn.execute(SCHEDULE_UPDATES_TABLE)
            await conn.execute(CURRENT_WEEK_TABLE)
            
            # Восстанавливаем группы
            if existing_groups:
                await conn.executemany(
                    "INSERT INTO groups (name) VALUES ($1) ON CONFLICT (name) DO NOTHING",
                    [(group,) for group in existing_groups]
                )
            
            # Инициализируем текущую неделю с сохраненным значением
            await conn.execute("""
                INSERT INTO current_week (id, week_number, changed_at)
                VALUES (1, $1, NOW())
                ON CONFLICT (id) DO UPDATE 
                SET week_number = $1, changed_at = NOW();
            """, current_week)
            
            # Добавляем индексы для оптимизации
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_schedule_group_day ON schedule(group_name, day_of_week);
                CREATE INDEX IF NOT EXISTS idx_schedule_group ON schedule(group_name);
                CREATE INDEX IF NOT EXISTS idx_schedule_week ON schedule(week_number);
                CREATE INDEX IF NOT EXISTS idx_schedule_subject ON schedule(subject_id);
                CREATE INDEX IF NOT EXISTS idx_schedule_teacher ON schedule(teacher_id);
                CREATE INDEX IF NOT EXISTS idx_users_group ON users(group_name);
                CREATE INDEX IF NOT EXISTS idx_replacements_group_date ON replacements(group_name, date);
            """)
            
            # Инициализируем расписание после создания таблиц
            try:
                from .parsers.schedule import fetch_schedule
                print("Загружаем начальное расписание...")
                schedule_data = await fetch_schedule()
                if schedule_data:
                    await store_schedule(pool, schedule_data)
                    print("Начальное расписание загружено")
                else:
                    print("Не удалось загрузить начальное расписание")
            except Exception as e:
                print(f"Ошибка при загрузке начального расписания: {e}")
                # Продолжаем работу даже при ошибке загрузки расписания

async def update_groups_list(pool, groups):
    """Обновляет список групп в базе данных"""
    async with pool.acquire() as conn:
        # Минимизируем транзакции и используем UPSERT
        if groups:
            await conn.executemany(
                "INSERT INTO groups (name) VALUES ($1) ON CONFLICT (name) DO NOTHING",
                [(group,) for group in groups]
            )

def clear_schedule_cache():
    """Очищает кэш расписания"""
    global _schedule_cache
    _schedule_cache = {}

def clear_week_cache():
    """Очищает кэш текущей недели"""
    global _current_week_cache
    _current_week_cache = {'value': None, 'timestamp': 0}

async def update_current_week(pool):
    """Обновляет номер текущей недели"""
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE current_week 
            SET week_number = CASE 
                WHEN week_number = 1 THEN 2 
                ELSE 1 
            END,
            changed_at = NOW()
            WHERE id = 1
        """)
        
    # Очищаем кэши после обновления недели
    clear_week_cache()
    clear_schedule_cache()

# Кэш для текущей недели
_current_week_cache = {'value': None, 'timestamp': 0}
_week_cache_ttl = 60  # 1 минута

async def get_current_week(pool):
    """Получает номер текущей недели"""
    from time import time
    
    # Проверяем кэш
    if _current_week_cache['value'] is not None:
        if time() - _current_week_cache['timestamp'] < _week_cache_ttl:
            return _current_week_cache['value']
    
    async with pool.acquire() as conn:
        value = await conn.fetchval("""
            SELECT week_number FROM current_week WHERE id = 1
        """)
        
        # Обновляем кэш
        _current_week_cache['value'] = value
        _current_week_cache['timestamp'] = time()
        
        return value

async def get_or_create_subject(pool, subject_name):
    """Получает или создает запись о предмете"""
    async with pool.acquire() as conn:
        # Пробуем найти существующий предмет
        subject_id = await conn.fetchval(
            "SELECT id FROM subjects WHERE name = $1",
            subject_name
        )
        if not subject_id:
            # Создаем новый предмет
            subject_id = await conn.fetchval(
                "INSERT INTO subjects (name) VALUES ($1) RETURNING id",
                subject_name
            )
        return subject_id

async def get_or_create_teacher(pool, teacher_name):
    """Получает или создает запись о преподавателе"""
    if not teacher_name:
        return None
        
    async with pool.acquire() as conn:
        # Пробуем найти существующего преподавателя
        teacher_id = await conn.fetchval(
            "SELECT id FROM teachers WHERE name = $1",
            teacher_name
        )
        if not teacher_id:
            # Создаем нового преподавателя
            teacher_id = await conn.fetchval(
                "INSERT INTO teachers (name) VALUES ($1) RETURNING id",
                teacher_name
            )
        return teacher_id

async def store_schedule(pool, schedule_data):
    """Сохраняет расписание в БД"""
    if not schedule_data:
        print("Нет данных для сохранения")
        return
        
    # Подготавливаем данные для массовой вставки
    schedule_values = []
    subject_names = set()
    teacher_names = set()
    
    try:
        # Валидация структуры данных
        if not isinstance(schedule_data, dict):
            print("Ошибка: неверный формат данных расписания")
            return
            
        if not schedule_data:
            print("Ошибка: пустой словарь расписания")
            return
            
        # Получаем хеш файла из данных
        try:
            first_group = next(iter(schedule_data))
            first_day = next(iter(schedule_data[first_group]))
            first_lesson = schedule_data[first_group][first_day][0]
            file_hash = first_lesson.get('file_hash', '')
        except (StopIteration, KeyError, IndexError) as e:
            print(f"Ошибка при получении хеша файла: {e}")
            return
            
    except Exception as e:
        print(f"Ошибка при подготовке данных: {e}")
        return
        
    async with pool.acquire() as conn:
        async with conn.transaction():
            try:
                # Проверка хеша файла
                if not file_hash:
                    print("Ошибка: отсутствует хеш файла")
                    return
                
                if not file_hash:
                    print("Ошибка: отсутствует хеш файла")
                    return
                
                # Проверяем изменения
                existing_hash = await conn.fetchval("SELECT file_hash FROM schedule LIMIT 1")
                if existing_hash == file_hash:
                    print("Расписание не изменилось")
                    return

                # Очищаем старое расписание
                await conn.execute("DELETE FROM schedule")

                print("Начинаем сохранение расписания в БД...")
                
                print("Количество найденных групп:", len(schedule_data))
                
                # Собираем все предметы и преподавателей
                for group, days in schedule_data.items():
                    if not isinstance(days, dict):
                        print(f"Пропуск группы {group}: неверный формат данных")
                        continue
                        
                    for day, lessons in days.items():
                        if not isinstance(lessons, list):
                            print(f"Пропуск дня {day} для группы {group}: неверный формат данных")
                            continue
                            
                        for lesson in lessons:
                            if not isinstance(lesson, dict):
                                print(f"Пропуск урока для группы {group} в день {day}: неверный формат данных")
                                continue
                                
                            subject = lesson.get('subject', '').strip()
                            teacher = lesson.get('teacher', '').strip()
                            
                            if subject:
                                subject_names.add(subject)
                            if teacher:
                                teacher_names.add(teacher)
                                
                print("Найдено предметов:", len(subject_names))
                print("Найдено преподавателей:", len(teacher_names))
                
            except Exception as e:
                print(f"Ошибка при сборе данных о предметах и преподавателях: {e}")
                raise
                            
            # Массово создаем предметы и преподавателей
            await conn.executemany(
                "INSERT INTO subjects (name) VALUES ($1) ON CONFLICT (name) DO NOTHING",
                [(name,) for name in subject_names]
            )
            await conn.executemany(
                "INSERT INTO teachers (name) VALUES ($1) ON CONFLICT (name) DO NOTHING",
                [(name,) for name in teacher_names]
            )
            
            # Получаем словари с id предметов и преподавателей
            subjects = await conn.fetch("SELECT id, name FROM subjects WHERE name = ANY($1)", list(subject_names))
            teachers = await conn.fetch("SELECT id, name FROM teachers WHERE name = ANY($1)", list(teacher_names))
            
            subject_ids = {s['name']: s['id'] for s in subjects}
            teacher_ids = {t['name']: t['id'] for t in teachers}
            
            # Обрабатываем данные
            for group, days in schedule_data.items():
                has_two_week_schedule = any(
                    any(lesson.get('week_number') == 2 for lesson in lessons)
                    for lessons in days.values()
                )

                for day, lessons in days.items():
                    for lesson in lessons:
                        # Получаем id предмета и преподавателя
                        subject_id = subject_ids.get(lesson['subject'])
                        teacher_id = teacher_ids.get(lesson.get('teacher'))
                        
                        # Определяем номер недели
                        week_number = lesson.get('week_number', 1)
                        week_numbers = [1, 2] if not has_two_week_schedule else [week_number]
                            
                        for week in week_numbers:
                            schedule_values.append((
                                group, day, lesson['lesson_number'],
                                subject_id, teacher_id, lesson['room'],
                                lesson['start_time'], lesson['end_time'], week,
                                has_two_week_schedule, file_hash
                            ))
            
            # Массовая вставка расписания
            await conn.executemany("""
                INSERT INTO schedule (
                    group_name, day_of_week, lesson_number,
                    subject_id, teacher_id, classroom,
                    start_time, end_time, week_number,
                    has_two_week_schedule, file_hash
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """, schedule_values)
            
            # Очищаем кэш после обновления
            clear_schedule_cache()

# Кэш для расписания: {(group_name, day_of_week, week_number): (data, timestamp)}
_schedule_cache = {}
_cache_ttl = 300  # 5 минут

async def get_schedule(pool, group_name, day_of_week=None, week_number=None):
    """Получает расписание из БД с учетом недели"""
    from time import time
    
    # Проверяем кэш
    cache_key = (group_name, day_of_week, week_number)
    if cache_key in _schedule_cache:
        data, timestamp = _schedule_cache[cache_key]
        if time() - timestamp < _cache_ttl:
            return data
    
    async with pool.acquire() as conn:
        # Если неделя не указана, получаем текущую
        if week_number is None:
            week_number = await get_current_week(pool)
            
        # Базовый запрос с JOIN для получения информации о предметах и преподавателях
        base_query = """
            SELECT 
                s.group_name,
                s.day_of_week,
                s.lesson_number,
                subj.name as subject,
                t.name as teacher,
                s.classroom,
                s.start_time,
                s.end_time,
                s.week_number,
                s.has_two_week_schedule
            FROM schedule s
            LEFT JOIN subjects subj ON s.subject_id = subj.id
            LEFT JOIN teachers t ON s.teacher_id = t.id
            WHERE s.group_name = $1
        """
        
        if day_of_week:
            # Для конкретного дня
            query = base_query + """
                AND s.day_of_week = $2
                AND (
                    (s.has_two_week_schedule AND s.week_number = $3)
                    OR (NOT s.has_two_week_schedule)
                )
                ORDER BY s.lesson_number
            """
            rows = await conn.fetch(query, group_name, day_of_week, week_number)
        else:
            # Для всех дней
            query = base_query + """
                AND (
                    (s.has_two_week_schedule AND s.week_number = $2)
                    OR (NOT s.has_two_week_schedule)
                )
                ORDER BY s.day_of_week, s.lesson_number
            """
            rows = await conn.fetch(query, group_name, week_number)
        
        result = [dict(row) for row in rows]
        
        # Сохраняем в кэш
        _schedule_cache[cache_key] = (result, time())
        
        return result
