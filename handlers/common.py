import logging
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.models import User, Log
from keyboards.inline import main_menu_keyboard, settings_keyboard, admin_keyboard
from core.config import ADMIN_IDS

logger = logging.getLogger(__name__)
router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message, session: AsyncSession, state: FSMContext):
    """Обработчик команды /start."""
    await state.clear()
    user_id = message.from_user.id
    
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        user = User(id=user_id)
        session.add(user)
        await session.commit()
        logger.info(f"Новый пользователь: {user_id}")

    session.add(Log(user_id=user_id, action="start"))
    await session.commit()

    text = (
        f"👋 Привет, {message.from_user.full_name}!\n\n"
        "Я помогу тебе узнать расписание занятий, замены и другую полезную информацию по колледжу.\n"
        "\nВыбери свою группу или воспользуйся меню для навигации."
    )
    keyboard = main_menu_keyboard(is_group_selected=bool(user.group_name))
    await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    """Возврат в главное меню."""
    await state.clear()
    result = await session.execute(select(User).where(User.id == callback.from_user.id))
    user = result.scalar_one_or_none()
    
    text = "Вы в главном меню."
    keyboard = main_menu_keyboard(is_group_selected=bool(user.group_name))
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "settings")
async def settings_menu(callback: types.CallbackQuery, session: AsyncSession):
    """Обработчик кнопки 'Настройки'."""
    session.add(Log(user_id=callback.from_user.id, action="settings"))
    await session.commit()
    
    await callback.message.edit_text("⚙️ Настройки", reply_markup=settings_keyboard())
    await callback.answer()

@router.callback_query(F.data == "my_profile")
async def my_profile(callback: types.CallbackQuery, session: AsyncSession):
    """Показывает профиль пользователя."""
    user_id = callback.from_user.id
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    session.add(Log(user_id=user_id, action="view_profile"))
    await session.commit()

    if user:
        join_date_str = user.join_date.strftime("%d.%m.%Y")
        text = (
            f"👤 **Ваш профиль:**\n\n"
            f"**ID:** `{user.id}`\n"
            f"👥 **Группа:** {user.group_name or 'Не выбрана'}\n"
            f"📅 **Дата регистрации:** {join_date_str}"
        )
        await callback.message.edit_text(text, parse_mode="Markdown")
    await callback.answer()

@router.message(Command("admin"))
async def admin_panel(message: types.Message):
    """Вход в админ-панель."""
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("У вас нет прав доступа.")
        return
    await message.answer("Добро пожаловать в админ-панель!", reply_markup=admin_keyboard())

@router.callback_query(F.data == "admin_menu")
async def admin_menu_callback(callback: types.CallbackQuery):
    """Возврат в админ-панель."""
    if str(callback.from_user.id) not in ADMIN_IDS:
        await callback.answer("У вас нет прав доступа.", show_alert=True)
        return
    await callback.message.edit_text("Админ-панель", reply_markup=admin_keyboard())
    await callback.answer()
