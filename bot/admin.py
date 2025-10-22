from aiogram import Router, types
from aiogram.filters import Command
import asyncpg
import os

router = Router()

ADMINS = [int(x) for x in os.getenv("ADMINS", "").split(",") if x]

def admin_only(func):
    async def wrapper(message: types.Message, *args, **kwargs):
        if message.from_user.id not in ADMINS:
            await message.answer("⛔️ Доступ только для админов!")
            return
        return await func(message, *args, **kwargs)
    return wrapper

@router.message(Command("stats"))
@admin_only
async def stats(message: types.Message, bot):
    pool: asyncpg.Pool = message.bot.dispatcher['db']
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM users")
        today = await conn.fetchval("SELECT COUNT(*) FROM users WHERE joined_at::date = CURRENT_DATE")
        week = await conn.fetchval("SELECT COUNT(*) FROM users WHERE joined_at >= CURRENT_DATE - INTERVAL '7 days'")
        students = await conn.fetchval("SELECT COUNT(*) FROM users WHERE role='student'")
        teachers = await conn.fetchval("SELECT COUNT(*) FROM users WHERE role='teacher'")
        no_role = await conn.fetchval("SELECT COUNT(*) FROM users WHERE role IS NULL")
        group_rows = await conn.fetch("SELECT group_name, COUNT(*) as cnt FROM users WHERE group_name IS NOT NULL GROUP BY group_name ORDER BY cnt DESC")
    text = f"<b>📊 Статистика пользователей:</b>\n"
    text += f"Всего: <b>{total}</b>\n"
    text += f"Новых сегодня: <b>{today}</b>\n"
    text += f"Активных за неделю: <b>{week}</b>\n"
    text += f"Учеников: <b>{students}</b>\nПреподавателей: <b>{teachers}</b>\nБез роли: <b>{no_role}</b>\n"
    text += "\n<b>Группы:</b>\n"
    for row in group_rows:
        text += f"{row['group_name']}: <b>{row['cnt']}</b>\n"
    await message.answer(text, parse_mode="HTML")

@router.message(Command("groups"))
@admin_only
async def group_stats(message: types.Message, bot):
    pool: asyncpg.Pool = message.bot.dispatcher['db']
    async with pool.acquire() as conn:
        group_rows = await conn.fetch("SELECT group_name, COUNT(*) as cnt FROM users WHERE group_name IS NOT NULL GROUP BY group_name ORDER BY cnt DESC")
    text = "<b>📚 Статистика по группам:</b>\n"
    for row in group_rows:
        text += f"{row['group_name']}: <b>{row['cnt']}</b>\n"
    await message.answer(text, parse_mode="HTML")

    # The group_stats function and its command handler have been removed.
