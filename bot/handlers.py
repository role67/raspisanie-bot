import logging
from aiogram import Router, F, types
from aiogram.filters import CommandStart
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
async def main_schedule(message: types.Message, bot):
    await message.answer("📅 Для просмотра расписания выберите свою группу через /start или используйте меню выбора группы.")

@router.message(F.text == "Замены ✏️")
async def main_replacements(message: types.Message, bot):
    await message.answer("🔄 Для просмотра замен выберите свою группу через /start или используйте меню выбора группы.")

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
async def main_profile(message: types.Message, bot):
    await message.answer("👤 Для просмотра профиля используйте команду /profile.")

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

from .parsers.schedule import fetch_schedule, fetch_replacements

async def get_schedule_text(group: str) -> str:
    """Формирует текст расписания для группы"""
    from .parsers.lesson_times import LESSON_TIMES
    schedule_data = fetch_schedule()
    replacements_data = fetch_replacements()
    
    if group not in schedule_data:
        return "❌ Расписание для группы не найдено"
    
    text = f"📅 Расписание для группы {group}:\n\n"
    
    # Сгруппируем пары по номерам
    lessons_by_number = {}
    for lesson in schedule_data[group]:
        time = lesson['time']
        if time not in lessons_by_number:
            lessons_by_number[time] = []
        lessons_by_number[time].append(lesson)
    
    # Добавляем основное расписание
    for time, lessons in lessons_by_number.items():
        text += f"{'_' * 7} Занятие №{time[0]} {'_' * 7}\n"
        text += f"         ⏰«{LESSON_TIMES.get(time, 'Время не указано')}»\n\n"
        
        for lesson in lessons:
            subject = lesson.get('subject', '').strip()
            teacher = lesson.get('teacher', '').strip()
            room = lesson.get('room', '').strip()
            
            if subject and subject != "-----":
                text += f"📚 Предмет: {subject}\n"
                if teacher:
                    text += f"👤 Преподаватель: {teacher}\n"
                if room:
                    text += f"🚪 Кабинет: {room}\n"
                text += "\n"
        text += "\n"
    
    # Добавляем замены, если есть
    if group in replacements_data:
        text += "\n🔄 ЗАМЕНЫ В РАСПИСАНИИ:\n"
        for date, replacements in replacements_data[group].items():
            text += f"\n📅 {date}:\n"
            for rep in replacements:
                text += f"{'_' * 7} Занятие №{rep['lesson']} {'_' * 7}\n"
                text += f"         ⏰«{LESSON_TIMES.get(f'{rep['lesson']} пара', 'Время не указано')}»\n\n"
                text += f"📚 Предмет: {rep['subject']}\n"
                if rep.get('teacher'):
                    text += f"👤 Преподаватель: {rep['teacher']}\n"
                text += f"🚪 Кабинет: {rep['room']}\n\n"
    
    return text

@router.callback_query(F.data.startswith("group_"))
async def choose_group(callback: types.CallbackQuery, state: FSMContext, db=None):
    try:
        # Отвечаем на callback немедленно
        await callback.answer()
        
        group = callback.data.replace("group_", "")
        
        if not db:
            await callback.message.edit_text("Ошибка подключения к базе данных")
            return
            
        # Сохраняем выбор группы
        await db.execute(
            """
            INSERT INTO users (user_id, group_name) 
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET group_name = $2
            """,
            callback.from_user.id, group
        )
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
    group = callback.data.replace("schedule_", "")
    
    # Показываем статус загрузки
    await callback.answer("⏳ Загружаю расписание...")
    
    # Получаем расписание
    schedule_text = await get_schedule_text(group)
    
    # Создаем клавиатуру для возврата
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Обновить расписание", callback_data=f"schedule_{group}")
    builder.button(text="📚 Выбрать другую группу", callback_data="show_groups")
    
    await callback.message.edit_text(
        schedule_text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
