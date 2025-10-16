from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def main_menu_keyboard(is_group_selected: bool):
    """Генерирует главную клавиатуру."""
    builder = InlineKeyboardBuilder()
    if not is_group_selected:
        builder.row(InlineKeyboardButton(text="🎓 Выбрать группу", callback_data="select_group"))
    builder.row(
        InlineKeyboardButton(text="📝 Расписание", callback_data="get_schedule"),
        InlineKeyboardButton(text="🕑 Время", callback_data="get_time")
    )
    builder.row(InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings"))
    return builder.as_markup()

def settings_keyboard():
    """Генерирует клавиатуру настроек."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👤 Мой профиль", callback_data="my_profile"))
    builder.row(InlineKeyboardButton(text="🔄 Сменить группу", callback_data="select_group"))
    builder.row(InlineKeyboardButton(text="😔 Поддержка", callback_data="support"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu"))
    return builder.as_markup()

def group_selection_keyboard(groups: list, page: int = 0, page_size: int = 15):
    """Генерирует клавиатуру для выбора группы с пагинацией."""
    builder = InlineKeyboardBuilder()
    start = page * page_size
    end = start + page_size
    
    for group in groups[start:end]:
        builder.row(InlineKeyboardButton(text=group, callback_data=f"group_selected:{group}"))

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"group_page:{page-1}"))
    if end < len(groups):
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"group_page:{page+1}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)
        
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu"))
    return builder.as_markup()

def time_keyboard():
    """Клавиатура для раздела 'Время' с кнопкой 'Все звонки'."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔔 Все звонки", callback_data="all_bells"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu"))
    return builder.as_markup()

def back_to_main_menu_keyboard():
    """Клавиатура с кнопкой 'Назад'."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu"))
    return builder.as_markup()

def admin_keyboard():
    """Клавиатура для администратора."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    builder.row(InlineKeyboardButton(text="🔄 Принудительный парсинг", callback_data="force_parse"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu"))
    return builder.as_markup()

def admin_stats_keyboard():
    """Клавиатура статистики для администратора."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👥 Пользователи по группам", callback_data="admin_stats_by_group"))
    builder.row(InlineKeyboardButton(text="📈 Общая активность", callback_data="admin_stats_activity"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад в админ-меню", callback_data="admin_menu"))
    return builder.as_markup()
