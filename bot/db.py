
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
    joined_at TIMESTAMP DEFAULT NOW()
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
            
            # Инициализируем текущую неделю (2-я неделя)
            await conn.execute("""
                INSERT INTO current_week (id, week_number, changed_at)
                VALUES (1, 2, NOW())
                ON CONFLICT (id) DO UPDATE 
                SET week_number = 2, changed_at = NOW();
            """)
            
            # Добавляем индексы для оптимизации
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_schedule_group_day 
                ON schedule(group_name, day_of_week);
                
                CREATE INDEX IF NOT EXISTS idx_schedule_group 
                ON schedule(group_name);
                
                CREATE INDEX IF NOT EXISTS idx_schedule_week 
                ON schedule(week_number);
                
                CREATE INDEX IF NOT EXISTS idx_schedule_subject 
                ON schedule(subject_id);
                
                CREATE INDEX IF NOT EXISTS idx_schedule_teacher 
                ON schedule(teacher_id);
            """)

async def update_groups_list(pool, groups):
    """Обновляет список групп в базе данных"""
    async with pool.acquire() as conn:
        # Начинаем транзакцию
        async with conn.transaction():
            # Очищаем таблицу
            await conn.execute("DELETE FROM groups")
            # Добавляем новые группы
            if groups:
                await conn.executemany(
                    "INSERT INTO groups (name) VALUES ($1)",
                    [(group,) for group in groups]
                )

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

async def get_current_week(pool):
    """Получает номер текущей недели"""
    async with pool.acquire() as conn:
        return await conn.fetchval("""
            SELECT week_number FROM current_week WHERE id = 1
        """)

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
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Получаем хеш файла
            file_hash = next(iter(next(iter(schedule_data.values())).values()))[0].get('file_hash')
            
            # Проверяем изменения
            existing_hash = await conn.fetchval("SELECT file_hash FROM schedule LIMIT 1")
            if existing_hash == file_hash:
                print("Расписание не изменилось")
                return

            # Очищаем старое расписание
            await conn.execute("DELETE FROM schedule")
            
            # Обрабатываем данные
            for group, days in schedule_data.items():
                has_two_week_schedule = False
                
                # Проверяем, есть ли у группы разное расписание по неделям
                for day, lessons in days.items():
                    if any(lesson.get('week_number') == 2 for lesson in lessons):
                        has_two_week_schedule = True
                        break

                for day, lessons in days.items():
                    for lesson in lessons:
                        # Получаем или создаем записи для предмета и преподавателя
                        subject_id = await get_or_create_subject(pool, lesson['subject'])
                        teacher_id = await get_or_create_teacher(pool, lesson['teacher'])
                        
                        # Определяем номер недели
                        week_number = lesson.get('week_number', 1)
                        if not has_two_week_schedule:
                            # Если нет разделения по неделям, создаем записи для обеих недель
                            week_numbers = [1, 2]
                        else:
                            week_numbers = [week_number]
                            
                        for week in week_numbers:
                            await conn.execute("""
                                INSERT INTO schedule (
                                    group_name, day_of_week, lesson_number,
                                    subject_id, teacher_id, classroom,
                                    start_time, end_time, week_number,
                                    has_two_week_schedule, file_hash
                                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                            """,
                            group, day, lesson['lesson_number'],
                            subject_id, teacher_id, lesson['room'],
                            lesson['start_time'], lesson['end_time'], week,
                            has_two_week_schedule, file_hash)

async def get_schedule(pool, group_name, day_of_week=None, week_number=None):
    """Получает расписание из БД с учетом недели"""
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
        
        return [dict(row) for row in rows]
