from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

class DbMiddleware(BaseMiddleware):
    def __init__(self, pool):
        super().__init__()
        self.pool = pool

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        if not self.pool:
            print("Warning: Database pool is not initialized")
            return await handler(event, data)
        
        # Сохраняем пул в данных события и в данных бота
        data["pool"] = self.pool
        if isinstance(event, Message):
            event.bot.db_pool = self.pool
        elif isinstance(event, CallbackQuery):
            event.bot.db_pool = self.pool
            
        try:
            return await handler(event, data)
        except Exception as e:
            print(f"Error in middleware: {e}")
            if isinstance(event, CallbackQuery):
                await event.answer("Произошла ошибка при обработке запроса", show_alert=True)
            elif isinstance(event, Message):
                await event.answer("Произошла ошибка при обработке сообщения")
            return None
