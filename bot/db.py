import asyncpg

USER_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    group_name TEXT,
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
        await conn.execute(USER_TABLE)
        await conn.execute(SCHEDULE_TABLE)
        await conn.execute(REPLACEMENTS_TABLE)
