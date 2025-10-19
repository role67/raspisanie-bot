from aiogram import Router, F, types
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import Bot
from datetime import datetime
import asyncpg
import os

router = Router()

class ProfileStates(StatesGroup):
    choosing_group = State()

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext, bot: Bot, pool=None):
    await message.answer("👋 Привет! Я бот расписания колледжа. Выберите свою группу:", reply_markup=await group_keyboard(pool))
    await state.set_state(ProfileStates.choosing_group)

async def group_keyboard(pool):
    # Получаем группы из базы данных
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT DISTINCT group_name FROM schedule ORDER BY group_name")
    builder = InlineKeyboardBuilder()
    for row in rows:
        builder.button(text=row['group_name'], callback_data=f"group_{row['group_name']}")
    return builder.as_markup()

@router.callback_query(F.data.startswith("group_"))
async def choose_group(callback: types.CallbackQuery, state: FSMContext, bot: Bot, pool=None):
    group = callback.data.replace("group_", "")
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO users (user_id, group_name) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET group_name = $2", callback.from_user.id, group)
    await callback.message.edit_text(f"✅ Ваша группа: <b>{group}</b>\nТеперь вы можете узнать расписание и другую информацию!", parse_mode="HTML")
    await state.clear()
