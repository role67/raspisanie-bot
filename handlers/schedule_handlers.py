from aiogram import Router, F, types
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from core.models import User, Group, Schedule, Replacement, Log
from keyboards.inline import (group_selection_keyboard, back_to_main_menu_keyboard,
                              time_keyboard)
from utils.time_helpers import get_time_status, BELLS_TEXT, get_current_week_type

router = Router()

class GroupSelection(StatesGroup):
    choosing_group = State()

@router.callback_query(F.data == "get_schedule")
async def get_schedule(callback: types.CallbackQuery, session: AsyncSession):
    """Показывает расписание для группы пользователя."""
    user_id = callback.from_user.id
    user = await session.get(User, user_id)

    if not user or not user.group_name:
        await callback.answer("Сначала выберите группу в настройках.", show_alert=True)
        return

    session.add(Log(user_id=user_id, action="view_schedule"))
    await session.commit()

    # Здесь должна быть логика получения расписания из БД
    # и его форматирования с учетом замен.
    # Это упрощенный пример.
    week_type = get_current_week_type()
    text = f"📝 Расписание для группы **{user.group_name}** на *{week_type}* неделю:\n\n"
    text += "ℹ️ _Данные о расписании временно недоступны. Парсер в разработке._"
    
    await callback.message.edit_text(text, reply_markup=back_to_main_menu_keyboard(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "get_time")
async def get_time(callback: types.CallbackQuery, session: AsyncSession):
    """Показывает время до начала/конца пары и инлайн-кнопку 'Все звонки'."""
    session.add(Log(user_id=callback.from_user.id, action="view_time"))
    await session.commit()
    
    status_text = get_time_status()
    # Используем клавиатуру с кнопкой "🔔 Все звонки"
    await callback.message.edit_text(status_text, reply_markup=time_keyboard())
    await callback.answer()

@router.callback_query(F.data == "all_bells")
async def all_bells(callback: types.CallbackQuery):
    """Показывает расписание всех звонков."""
    await callback.message.edit_text(BELLS_TEXT, reply_markup=time_keyboard(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "select_group")
async def select_group_start(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    """Начинает процесс выбора группы."""
    await state.set_state(GroupSelection.choosing_group)
    
    result = await session.execute(select(Group.name).order_by(Group.name))
    groups = [row[0] for row in result]
    
    await callback.message.edit_text(
        "Выберите вашу группу:",
        reply_markup=group_selection_keyboard(groups, page=0)
    )
    await callback.answer()

@router.callback_query(GroupSelection.choosing_group, F.data.startswith("group_page:"))
async def paginate_groups(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    """Пагинация списка групп."""
    page = int(callback.data.split(":")[1])
    
    result = await session.execute(select(Group.name).order_by(Group.name))
    groups = [row[0] for row in result]
    
    await callback.message.edit_text(
        "Выберите вашу группу:",
        reply_markup=group_selection_keyboard(groups, page=page)
    )
    await callback.answer()

@router.callback_query(GroupSelection.choosing_group, F.data.startswith("group_selected:"))
async def group_selected(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    """Обрабатывает выбор группы."""
    group_name = callback.data.split(":")[1]
    user_id = callback.from_user.id

    user = await session.get(User, user_id)
    old_group = user.group_name

    if old_group and old_group != group_name:
        await session.execute(
            update(Group).where(Group.name == old_group).values(student_count=Group.student_count - 1)
        )

    user.group_name = group_name
    await session.execute(
        update(Group).where(Group.name == group_name).values(student_count=Group.student_count + 1)
    )
    
    session.add(Log(user_id=user_id, action=f"select_group:{group_name}"))
    await session.commit()
    
    await state.clear()
    await callback.message.edit_text(f"✅ Вы выбрали группу: {group_name}", reply_markup=back_to_main_menu_keyboard())
    await callback.answer()
