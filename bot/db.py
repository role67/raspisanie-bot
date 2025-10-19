
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

SCHEDULE_TABLE = """
CREATE TABLE IF NOT EXISTS schedule (
    id SERIAL PRIMARY KEY,
    group_name TEXT,
    day_of_week TEXT,
    lesson_number INT,
    subject TEXT,
    teacher TEXT,
    classroom TEXT,
    start_time TIME,
    end_time TIME
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

async def create_tables(pool):
    async with pool.acquire() as conn:
        await conn.execute(GROUPS_TABLE)
        await conn.execute(USER_TABLE)
        await conn.execute(SCHEDULE_TABLE)
        await conn.execute(REPLACEMENTS_TABLE)

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
