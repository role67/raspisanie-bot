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
        yesterday = await conn.fetchval("SELECT COUNT(*) FROM users WHERE joined_at::date = CURRENT_DATE - INTERVAL '1 day'")
        month = await conn.fetchval("SELECT COUNT(*) FROM users WHERE joined_at >= date_trunc('month', CURRENT_DATE)")
    await message.answer(f"📊 Статистика пользователей:\nСегодня: <b>{today}</b>\nВчера: <b>{yesterday}</b>\nЗа месяц: <b>{month}</b>\nВсего: <b>{total}</b>", parse_mode="HTML")

@router.message(Command("groups"))
@admin_only
async def group_stats(message: types.Message, bot):
    pool: asyncpg.Pool = message.bot.dispatcher['db']
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT group_name, COUNT(*) as cnt FROM users WHERE group_name IS NOT NULL GROUP BY group_name ORDER BY cnt DESC")
    text = "<b>👥 Пользователи по группам:</b>\n"
    for row in rows:
        text += f"{row['group_name']}: <b>{row['cnt']}</b>\n"
    await message.answer(text, parse_mode="HTML")
