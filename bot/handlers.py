import logging
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import Bot

router = Router()

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import os

ADMINS = [int(x) for x in os.getenv("ADMINS", "").split(",") if x]

def get_main_menu(is_admin: bool = False):
    # Кнопки для всех пользователей
    buttons = [
        [KeyboardButton(text="Расписание 📝"), KeyboardButton(text="Замены ✏️")],
        [KeyboardButton(text="Время 🕒"), KeyboardButton(text="Профиль 🧑")]
    ]
    # Можно добавить админские кнопки, если нужно
    if is_admin:
        buttons.append([KeyboardButton(text="Админ панель 🛠")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, input_field_placeholder="НКПТиУ Лучший")

class ProfileStates(StatesGroup):
    choosing_group = State()

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext, bot: Bot, pool=None):
    is_admin = message.from_user.id in ADMINS
    menu = get_main_menu(is_admin)
    # Создаем инлайн клавиатуру для выбора группы
    builder = InlineKeyboardBuilder()
    builder.button(text="📚 Выбрать группу", callback_data="show_groups")
    
    await message.answer(
        "👋 Привет! Я бот расписания колледжа. Выберите действие через меню ниже:",
        reply_markup=menu
    )
    await message.answer(
        "Нажмите кнопку ниже, чтобы выбрать вашу группу:",
        reply_markup=builder.as_markup()
    )

# Обработчики нажатий на кнопки главного меню
@router.message(F.text == "Расписание 📝")
@router.message(Command("schedule"))
async def main_schedule(message: types.Message, bot, db=None):
    if not db:
        await message.answer("Ошибка подключения к базе данных")
        return
    user = await db.fetchrow("SELECT group_name FROM users WHERE user_id = $1", message.from_user.id)
    if not user or not user['group_name']:
        builder = InlineKeyboardBuilder()
        builder.button(text="📚 Выбрать группу", callback_data="show_groups")
        await message.answer("Сначала выберите вашу группу:", reply_markup=builder.as_markup())
        return
    group = user['group_name']
    builder = InlineKeyboardBuilder()
    builder.button(text="Сегодня", callback_data=f"schedule_{group}_today")
    builder.button(text="Завтра", callback_data=f"schedule_{group}_tomorrow")
    builder.button(text="Неделя", callback_data=f"schedule_{group}_week")
    await message.answer("Выберите период расписания:", reply_markup=builder.as_markup())

@router.message(F.text == "Замены ✏️")
async def main_replacements(message: types.Message, bot, db=None):
    if not db:
        await message.answer("Ошибка подключения к базе данных")
        return
        
    user = await db.fetchrow("SELECT group_name FROM users WHERE user_id = $1", message.from_user.id)
    if not user or not user['group_name']:
        builder = InlineKeyboardBuilder()
        builder.button(text="📚 Выбрать группу", callback_data="show_groups")
        await message.answer(
            "Сначала выберите вашу группу:",
            reply_markup=builder.as_markup()
        )
        return
        
    # Check replacements for user's group
    group = user['group_name']
    replacements_data = fetch_replacements()
    
    if group not in replacements_data:
        await message.answer("✅ Замен для вашей группы нет")
        return
        
    text = f"🔄 Замены для группы {group}:\n\n"
    for date, replacements in replacements_data[group].items():
        text += f"📅 {date}:\n"
        for rep in replacements:
            text += f"{'_' * 7} Занятие №{rep['lesson']} {'_' * 7}\n"
            text += f"📚 Предмет: {rep['subject']}\n"
            if rep.get('teacher'):
                text += f"👤 Преподаватель: {rep['teacher']}\n"
            text += f"🚪 Кабинет: {rep['room']}\n\n"
            
    await message.answer(text)

from datetime import datetime
from .parsers.lesson_times import get_current_lesson_info, get_schedule_string

@router.message(F.text == "Время 🕒")
async def main_time(message: types.Message, bot):
    weekday = datetime.now().weekday()
    current_info = get_current_lesson_info()
    schedule = get_schedule_string(weekday)
    
    text = f"{current_info}\n\n{schedule}"
    await message.answer(text)


@router.message(F.text == "Профиль 🧑")
@router.message(Command("profile"))
async def main_profile(message: types.Message, bot, db=None):
    if not db:
        await message.answer("Ошибка подключения к базе данных")
        return
    user = await db.fetchrow("SELECT group_name FROM users WHERE user_id = $1", message.from_user.id)
    if not user or not user['group_name']:
        await message.answer("Вы не выбрали группу. Выберите группу через меню.")
        return
    builder = InlineKeyboardBuilder()
    builder.button(text="Изменить группу", callback_data="show_groups")
    await message.answer(f"👤 Ваш профиль:\nГруппа: <b>{user['group_name']}</b>", reply_markup=builder.as_markup(), parse_mode="HTML")

@router.message(F.text == "Админ панель 🛠")
async def main_admin_panel(message: types.Message, bot):
    if message.from_user.id in ADMINS:
        await message.answer("🛠 Добро пожаловать в админ-панель! Используйте /stats и /groups для статистики.")
    else:
        await message.answer("⛔️ Доступ только для админов!")

GROUPS_PER_PAGE = 15

@router.callback_query(F.data.startswith("page_"))
@router.callback_query(F.data == "show_groups")
async def show_groups_list(callback: types.CallbackQuery, state: FSMContext, db=None):
    try:
        # Отвечаем на callback немедленно
        await callback.answer()
        
        current_page = 0
        if callback.data.startswith("page_"):
            current_page = int(callback.data.split("_")[1])

        # Получаем список групп из базы
        if not db:
            await callback.message.edit_text("Ошибка подключения к базе данных")
            return
            
        groups = await db.fetch("SELECT name FROM groups ORDER BY name")
    except Exception as e:
        logging.error(f"Error in show_groups_list: {e}")
        try:
            await callback.message.edit_text(
                "Произошла ошибка при получении списка групп. Попробуйте позже."
            )
        except:
            pass
        return
            
    total_groups = len(groups)
    total_pages = (total_groups + GROUPS_PER_PAGE - 1) // GROUPS_PER_PAGE
    
    # Получаем группы для текущей страницы
    start_idx = current_page * GROUPS_PER_PAGE
    end_idx = min(start_idx + GROUPS_PER_PAGE, total_groups)
    current_groups = groups[start_idx:end_idx]
    
    builder = InlineKeyboardBuilder()
    
    # Добавляем кнопки групп, разделенные на две колонки
    mid_point = (len(current_groups) + 1) // 2
    left_column = current_groups[:mid_point]
    right_column = current_groups[mid_point:]
    
    # Добавляем кнопки попарно из левой и правой колонки
    for i in range(max(len(left_column), len(right_column))):
        row_buttons = []
        if i < len(left_column):
            row_buttons.append(InlineKeyboardButton(
                text=left_column[i]['name'],
                callback_data=f"group_{left_column[i]['name']}"
            ))
        if i < len(right_column):
            row_buttons.append(InlineKeyboardButton(
                text=right_column[i]['name'],
                callback_data=f"group_{right_column[i]['name']}"
            ))
        builder.row(*row_buttons)
    
    # Добавляем навигационные кнопки
    nav_buttons = []
    if current_page > 0:
        nav_buttons.append(InlineKeyboardButton(
            text="◀️",
            callback_data=f"page_{current_page-1}"
        ))
    if current_page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(
            text="▶️",
            callback_data=f"page_{current_page+1}"
        ))
    if nav_buttons:
        builder.row(*nav_buttons)
    
    page_info = f"Страница {current_page + 1} из {total_pages}"
    
    await callback.message.edit_text(
        f"Выберите вашу группу из списка:\n{page_info}",
        reply_markup=builder.as_markup()
    )

from .parsers.schedule import fetch_schedule, fetch_replacements, format_day_schedule

def get_schedule_text(group: str, day: str = None, date_str: str = None, lessons: list = None, last_update=None) -> str:
    """Формирует текст расписания для группы (без замен), формат с эмодзи и правильным порядком"""
    from .parsers.lesson_times import LESSON_TIMES, WEEKDAY_TIMES, SATURDAY_TIMES
    from datetime import datetime
    schedule_data = fetch_schedule()
    if group not in schedule_data:
        return "❌ Расписание для группы не найдено"
    # Определяем словарь времени
    if day == 'Понедельник':
        times_dict = LESSON_TIMES
    elif day == 'Суббота':
        times_dict = SATURDAY_TIMES
    else:
        times_dict = WEEKDAY_TIMES
    # Заголовок
    if date_str:
        lines = [f"📅 {date_str} | {day}\n"]
    else:
        lines = [f"📅 {day}\n"]
    lessons = lessons if lessons is not None else schedule_data[group].get(day, [])
    if not lessons:
        lines.append("\n❌ Расписание на этот день не найдено")
    for idx, lesson in enumerate(lessons, 1):
        subject = lesson.get('subject', '').strip()
        teacher = lesson.get('teacher', '').strip()
        room = lesson.get('room', '').strip()
        time = lesson.get('time', '').strip()
        if not subject or subject == "-----":
            continue
        # Время пары
        time_str = times_dict.get(time, time)
        # Формат кабинета
        if subject.lower().startswith('физ') and teacher and teacher.lower().startswith('видяков'):
            room_str = "Общежитие"
        elif room and room.lower() in ['общ', 'общ.', 'общага']:
            room_str = "Общежитие"
        elif room:
            room_str = f"Каб. {room}"
        else:
            room_str = ""
        # Эмодзи для номера пары
        num_emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]
        num = num_emoji[idx-1] if idx <= len(num_emoji) else f"{idx}"
        lines.append(f"{num} {subject} | {time_str}")
        if teacher:
            lines.append(f"👤 {teacher}")
        if room_str:
            lines.append(f"🚪 {room_str}")
        lines.append("")
    if last_update:
        lines.append(f"� Обновлено: {last_update.strftime('%d.%m.%Y %H:%M')}")
    return '\n'.join(lines)

@router.callback_query(F.data.startswith("group_"))
async def choose_group(callback: types.CallbackQuery, state: FSMContext, db=None):
    try:
        # Отвечаем на callback немедленно
        await callback.answer("⏳ Сохраняю выбор...")
        
        group = callback.data.replace("group_", "")
        
        if not db:
            await callback.message.edit_text("Ошибка подключения к базе данных")
            return
            
        # Проверяем существование группы
        group_exists = await db.fetchval("SELECT name FROM groups WHERE name = $1", group)
        if not group_exists:
            await callback.message.edit_text("❌ Выбранная группа не найдена в базе данных")
            return
            
        # Сохраняем выбор группы в транзакции
        async with db.transaction():
            await db.execute(
                """
                INSERT INTO users (user_id, group_name) 
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET group_name = $2
                """,
                callback.from_user.id, group
            )
            
        # Подтверждаем сохранение
        await callback.answer("✅ Группа сохранена!", show_alert=True)
            
    except Exception as e:
        logging.error(f"Error in choose_group: {e}")
        try:
            await callback.message.edit_text(
                "Произошла ошибка при сохранении группы. Попробуйте позже."
            )
        except:
            pass
        return
    
    # Создаем клавиатуру для просмотра расписания
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Показать расписание", callback_data=f"schedule_{group}")
    builder.button(text="📚 Выбрать другую группу", callback_data="show_groups")
    
    await callback.message.edit_text(
        f"✅ Ваша группа: <b>{group}</b>\n"
        f"Нажмите кнопку ниже, чтобы посмотреть расписание:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data.startswith("schedule_"))
async def show_schedule(callback: types.CallbackQuery, state: FSMContext, pool=None):
    from datetime import datetime, timedelta
    data = callback.data.split("_")
    group = data[1]
    view_type = data[2] if len(data) > 2 else "today"
    await callback.answer("⏳ Загружаю расписание...")

    schedule_data = fetch_schedule()
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    weekday_map = {
        0: 'Понедельник',
        1: 'Вторник',
        2: 'Среда',
        3: 'Четверг',
        4: 'Пятница',
        5: 'Суббота',
        6: 'Воскресенье'
    }

    if view_type == "today":
        day = weekday_map[today.weekday()]
        if today.weekday() == 6:
            day = "Понедельник"
        date_str = today.strftime('%d.%m.%Y')
        lessons = schedule_data.get(group, {}).get(day, [])
        last_update = today
        if pool:
            async with pool.acquire() as conn:
                update_time = await conn.fetchval(
                    "SELECT updated_at FROM schedule_updates ORDER BY updated_at DESC LIMIT 1"
                )
                if update_time:
                    last_update = update_time
        schedule_text = get_schedule_text(group, day, date_str, lessons, last_update)
    elif view_type == "tomorrow":
        day = weekday_map[tomorrow.weekday()]
        if tomorrow.weekday() == 6:
            day = "Понедельник"
        date_str = tomorrow.strftime('%d.%m.%Y')
        lessons = schedule_data.get(group, {}).get(day, [])
        last_update = today
        if pool:
            async with pool.acquire() as conn:
                update_time = await conn.fetchval(
                    "SELECT updated_at FROM schedule_updates ORDER BY updated_at DESC LIMIT 1"
                )
                if update_time:
                    last_update = update_time
        schedule_text = get_schedule_text(group, day, date_str, lessons, last_update)
    else:
        week_days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']
        texts = []
        last_update = today
        if pool:
            async with pool.acquire() as conn:
                update_time = await conn.fetchval(
                    "SELECT updated_at FROM schedule_updates ORDER BY updated_at DESC LIMIT 1"
                )
                if update_time:
                    last_update = update_time
        for d in week_days:
            lessons = schedule_data.get(group, {}).get(d, [])
            texts.append(get_schedule_text(group, d, None, lessons, last_update))
        schedule_text = '\n'.join(texts)

    builder = InlineKeyboardBuilder()
    if view_type == "today":
        builder.button(text="На завтра ➡️", callback_data=f"schedule_{group}_tomorrow")
        builder.button(text="На неделю 📅", callback_data=f"schedule_{group}_week")
    elif view_type == "tomorrow":
        builder.button(text="⬅️ На сегодня", callback_data=f"schedule_{group}_today")
        builder.button(text="На неделю 📅", callback_data=f"schedule_{group}_week")
    else:
        builder.button(text="⬅️ На сегодня", callback_data=f"schedule_{group}_today")
        builder.button(text="На завтра ➡️", callback_data=f"schedule_{group}_tomorrow")

    await callback.message.edit_text(
        schedule_text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@router.message(Command("stats"))
async def admin_stats(message: types.Message, db=None):
    if message.from_user.id not in ADMINS:
        await message.answer("⛔️ Доступ только для админов!")
        return
    if not db:
        await message.answer("Ошибка подключения к базе данных")
        return
    users_count = await db.fetchval("SELECT COUNT(*) FROM users")
    groups_count = await db.fetchval("SELECT COUNT(*) FROM groups")
    await message.answer(f"Статистика:\nПользователей: <b>{users_count}</b>\nГрупп: <b>{groups_count}</b>", parse_mode="HTML")

@router.message(Command("groups"))
async def admin_groups(message: types.Message, db=None):
    if message.from_user.id not in ADMINS:
        await message.answer("⛔️ Доступ только для админов!")
        return
    if not db:
        await message.answer("Ошибка подключения к базе данных")
        return
    groups = await db.fetch("SELECT name FROM groups ORDER BY name")
    text = "Список групп:\n" + "\n".join([g['name'] for g in groups])
    await message.answer(text)
