from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime
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
    builder.adjust(3)  # 3 кнопки в ряд для компактности
    return builder.as_markup()

# --- Регистрация пользователя после выбора группы ---
@router.callback_query(F.data.startswith("group_"))
async def choose_group_callback(callback: types.CallbackQuery, bot, state):
    group_name = callback.data.replace("group_", "")
    pool = bot.dispatcher['db']
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    # Регистрируем пользователя с ролью None и username
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (user_id, group_name, joined_at, role, username) VALUES ($1, $2, NOW(), NULL, $3) ON CONFLICT (user_id) DO UPDATE SET group_name = $2, joined_at = NOW(), username = $3",
            user_id, group_name, username
        )
    await callback.message.answer(f"✅ Ваша группа: <b>{group_name}</b> успешно выбрана!", parse_mode="HTML")
    await state.clear()

# --- Профиль с выбором роли ---
@router.message(F.text == "Профиль 🧑")
@router.message(Command("profile"))
async def profile(message: types.Message, bot):
    pool = bot.dispatcher['db']
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT group_name, role FROM users WHERE user_id=$1", message.from_user.id)
    group = user['group_name'] if user else 'Не выбрана'
    role = user['role'] if user and user['role'] else 'Не указана'
    builder = InlineKeyboardBuilder()
    builder.button(text="Выбрать роль", callback_data="choose_role")
    await message.answer(f"👤 Ваш профиль\nГруппа: <b>{group}</b>\nРоль: <b>{role}</b>", parse_mode="HTML", reply_markup=builder.as_markup())

@router.callback_query(F.data == "choose_role")
async def choose_role_callback(callback: types.CallbackQuery, bot):
    builder = InlineKeyboardBuilder()
    builder.button(text="Ученик", callback_data="role_student")
    builder.button(text="Преподаватель", callback_data="role_teacher")
    builder.adjust(2)
    await callback.message.answer("Выберите вашу роль:", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("role_"))
async def set_role_callback(callback: types.CallbackQuery, bot):
    role = callback.data.replace("role_", "")
    pool = bot.dispatcher['db']
    user_id = callback.from_user.id
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET role=$1 WHERE user_id=$2", role, user_id)
    await callback.message.answer(f"✅ Ваша роль теперь: <b>{'Ученик' if role=='student' else 'Преподаватель'}</b>", parse_mode="HTML")

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
        if not lessons:
            await message.answer("Занятия на сегодня закончились🎉🥳")
            return
        # Проверяем время начала и конца пар
        first_lesson = lessons[0]
        last_lesson = lessons[-1]
        if now < first_lesson['start_time']:
            minutes = int((datetime.combine(datetime.today(), first_lesson['start_time']) - datetime.combine(datetime.today(), now)).total_seconds() // 60)
            await message.answer(f"ℹ️ Сейчас первая пара\n⌛️ До конца: {minutes} минут", reply_markup=InlineKeyboardBuilder().button(text="Все звонки 📢", callback_data="all_bells").as_markup())
            return
        for idx, lesson in enumerate(lessons, 1):
            if lesson['start_time'] <= now < lesson['end_time']:
                minutes = int((datetime.combine(datetime.today(), lesson['end_time']) - datetime.combine(datetime.today(), now)).total_seconds() // 60)
                await message.answer(f"ℹ️ Сейчас {idx}-я пара\n⌛️ До конца: {minutes} минут", reply_markup=InlineKeyboardBuilder().button(text="Все звонки 📢", callback_data="all_bells").as_markup())
                return
        if now > last_lesson['end_time']:
            await message.answer("Занятия на сегодня закончились🎉🥳")
            return
@router.callback_query(F.data == "all_bells")
async def all_bells_callback(callback: types.CallbackQuery, bot):
    # Понедельник
    text1 = "📅 Понедельник:\n\nКлассный час - 8:30 - 9:15 😔\nОбщий классный час - 9:15 - 10:00 ☹️\n\n1️⃣ пара\n10:20 - 11:05\n11:20 - 12:05\n\nПерерыв между парами 25 минут\n\n2️⃣ пара\n12:30 - 13:15\n13:30 - 14:15\n\nПерерыв между парами 15 минут\n\n3️⃣ пара\n14:30 - 16:00"
    await callback.message.answer(text1)
    # Вторник-пятница
    text2 = "📅 Со вторника по пятницу:\n\n1️⃣ пара\n8:30 – 10:00\n\nПерерыв между парами 20 минут\n\n2️⃣ пара\n10:20 – 11:05\n11:20 - 12:05\n\nПерерыв между парами 25 минут\n\n3️⃣ пара\n12:30 – 13:15\n13:30 - 14:15\n\nПерерыв между парами 15 минут\n\n4️⃣ пара\n14:30 – 16:00"
    await callback.message.answer(text2)
