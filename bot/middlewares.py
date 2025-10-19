import logging
from typing import Callable, Awaitable, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from asyncpg.pool import Pool

class DbMiddleware(BaseMiddleware):
    def __init__(self, pool: Pool):
        self.pool = pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any]
    ) -> Any:
        async with self.pool.acquire() as conn:
            data['db'] = conn
            try:
                return await handler(event, data)
            except Exception as e:
                logging.error(f"Error in handler: {e}")
                try:
                    if hasattr(event, 'message'):
                        await event.message.answer(
                            "Произошла ошибка при обработке запроса. Попробуйте позже."
                        )
                except:
                    logging.error("Could not send error message to user")
            finally:
                if 'db' in data:
                    del data['db']