import logging
from typing import Callable, Awaitable, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from asyncpg import Pool

class DbMiddleware(BaseMiddleware):
    def __init__(self, pool: Pool):
        self.pool = pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any]
    ) -> Any:
        try:
            async with self.pool.acquire() as conn:
                data['db'] = conn
                result = await handler(event, data)
                return result
        except Exception as e:
            logging.exception("Error in middleware")
            await event.answer("Произошла ошибка при обработке запроса", show_alert=True)
        finally:
            # Ensure the connection is released back to the pool
            if 'db' in data:
                del data['db']
