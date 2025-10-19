import logging
from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import Bot

router = Router()

class ProfileStates(StatesGroup):
    choosing_group = State()

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext, bot: Bot, pool=None):
    builder = InlineKeyboardBuilder()
    builder.button(text="📚 Выбрать группу", callback_data="show_groups")
    await message.answer(
        "👋 Привет! Я бот расписания колледжа. Нажмите кнопку ниже, чтобы выбрать свою группу:",
        reply_markup=builder.as_markup()
    )

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
    
    # Добавляем кнопки групп, по 2 в ряд
    for i in range(0, len(current_groups), 2):
        row_buttons = []
        for group in current_groups[i:i+2]:
            row_buttons.append(InlineKeyboardButton(
                text=group['name'],
                callback_data=f"group_{group['name']}"
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
    schedule_data = fetch_schedule()
    replacements_data = fetch_replacements()
    
    if group not in schedule_data:
        return "❌ Расписание для группы не найдено"
    
    text = f"📅 Расписание для группы {group}:\n\n"
    
    # Добавляем основное расписание
    for lesson in schedule_data[group]:
        text += f"🕐 {lesson['time']}\n"
        text += f"📚 {lesson['subject']}\n\n"
    
    # Добавляем замены, если есть
    if group in replacements_data:
        text += "\n🔄 Замены:\n"
        for date, replacements in replacements_data[group].items():
            text += f"\n📅 {date}:\n"
            for rep in replacements:
                text += f"🕐 Пара {rep['lesson']}\n"
                text += f"📚 {rep['subject']}\n"
                text += f"🏫 Кабинет: {rep['room']}\n\n"
    
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
