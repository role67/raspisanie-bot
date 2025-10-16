import logging
from datetime import datetime, timedelta
from aiogram import Router, F, types
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from core.config import ADMIN_IDS
from core.models import User, Group, Log
from keyboards.inline import admin_stats_keyboard
from utils.parser import parse_job

logger = logging.getLogger(__name__)
router = Router()

# Middleware для проверки прав администратора
@router.callback_query.middleware()
async def admin_check(handler, event: types.CallbackQuery, data: dict):
    if event.data.startswith("admin_"):
        if str(event.from_user.id) not in ADMIN_IDS:
            await event.answer("Доступ запрещен.", show_alert=True)
            return
    return await handler(event, data)

@router.callback_query(F.data == "force_parse")
async def force_parse_handler(callback: types.CallbackQuery, session: AsyncSession):
    """Принудительный запуск парсинга."""
    if str(callback.from_user.id) not in ADMIN_IDS:
        await callback.answer("Доступ запрещен.", show_alert=True)
        return
        
    await callback.answer("Запускаю парсинг...", show_alert=True)
    try:
        await parse_job(session)
        await callback.message.answer("✅ Парсинг успешно завершен.")
    except Exception as e:
        logger.error(f"Ошибка принудительного парсинга: {e}")
        await callback.message.answer(f"❌ Ошибка при парсинге: {e}")

@router.callback_query(F.data == "admin_stats")
async def admin_stats_handler(callback: types.CallbackQuery, session: AsyncSession):
    """Отображение общей статистики."""
    total_users = await session.scalar(select(func.count(User.id)))
    
    today = datetime.utcnow().date()
    users_today = await session.scalar(
        select(func.count(User.id)).where(func.date(User.join_date) == today)
    )
    
    text = (
        f"📊 **Общая статистика:**\n\n"
        f"Всего пользователей: {total_users}\n"
        f"Новых за сегодня: {users_today}"
    )
    await callback.message.edit_text(text, reply_markup=admin_stats_keyboard(), parse_mode="Markdown")

@router.callback_query(F.data == "admin_stats_by_group")
async def stats_by_group(callback: types.CallbackQuery, session: AsyncSession):
    """Статистика пользователей по группам."""
    result = await session.execute(select(Group.name, Group.student_count).order_by(Group.name))
    groups = result.all()
    
    if not groups:
        await callback.answer("Нет данных по группам.", show_alert=True)
        return

    text = "👥 **Пользователи по группам:**\n\n"
    text += "\n".join([f"{name}: {count}" for name, count in groups if count > 0])
    
    await callback.message.edit_text(text, reply_markup=admin_stats_keyboard(), parse_mode="Markdown")

@router.callback_query(F.data == "admin_stats_activity")
async def stats_activity(callback: types.CallbackQuery, session: AsyncSession):
    """Статистика активности пользователей."""
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    yesterday_start = today_start - timedelta(days=1)
    month_start = datetime(now.year, now.month, 1)

    active_today = await session.scalar(
        select(func.count(Log.user_id.distinct())).where(Log.timestamp >= today_start)
    )
    active_yesterday = await session.scalar(
        select(func.count(Log.user_id.distinct())).where(Log.timestamp.between(yesterday_start, today_start))
    )
    active_month = await session.scalar(
        select(func.count(Log.user_id.distinct())).where(Log.timestamp >= month_start)
    )

    text = (
        f"📈 **Активность пользователей:**\n\n"
        f"За сегодня: {active_today}\n"
        f"За вчера: {active_yesterday}\n"
        f"За месяц: {active_month}"
    )
    await callback.message.edit_text(text, reply_markup=admin_stats_keyboard(), parse_mode="Markdown")
