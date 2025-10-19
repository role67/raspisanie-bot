from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
import asyncpg

router = Router()

@router.message(Command("profile"))
async def profile(message: types.Message, bot):
    pool: asyncpg.Pool = message.bot.dispatcher['db']
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT group_name FROM users WHERE user_id=$1", message.from_user.id)
    group = user['group_name'] if user else 'Не выбрана'
    await message.answer(f"👤 Ваш профиль\nГруппа: <b>{group}</b>", parse_mode="HTML")

@router.message(Command("support"))
async def support(message: types.Message):
    await message.answer("💬 По всем вопросам пишите: @support_username")

@router.message(Command("change_group"))
async def change_group(message: types.Message, bot, state):
    await message.answer("🔄 Выберите новую группу:", reply_markup=await group_keyboard(bot))
    await state.set_state("ProfileStates:choosing_group")

async def group_keyboard(bot):
    pool: asyncpg.Pool = bot.dispatcher['db']
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT DISTINCT group_name FROM schedule ORDER BY group_name")
    builder = InlineKeyboardBuilder()
    for row in rows:
        builder.button(text=row['group_name'], callback_data=f"group_{row['group_name']}")
    return builder.as_markup()

@router.message(Command("time"))
async def time_to_lesson(message: types.Message, bot):
    pool: asyncpg.Pool = message.bot.dispatcher['db']
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT group_name FROM users WHERE user_id=$1", message.from_user.id)
        if not user or not user['group_name']:
            await message.answer("Сначала выберите группу через /start")
            return
        now = datetime.now().time()
        lessons = await conn.fetch("SELECT lesson_number, start_time, end_time FROM schedule WHERE group_name=$1 AND day_of_week=$2 ORDER BY lesson_number", user['group_name'], datetime.now().strftime('%A'))
        for lesson in lessons:
            if now < lesson['start_time']:
                delta = datetime.combine(datetime.today(), lesson['start_time']) - datetime.combine(datetime.today(), now)
                await message.answer(f"⏳ До начала {lesson['lesson_number']} урока: {delta}")
                return
            elif lesson['start_time'] <= now < lesson['end_time']:
                delta = datetime.combine(datetime.today(), lesson['end_time']) - datetime.combine(datetime.today(), now)
                await message.answer(f"🔔 До конца {lesson['lesson_number']} урока: {delta}")
                return
        await message.answer("🎉 Уроки на сегодня закончились!")
