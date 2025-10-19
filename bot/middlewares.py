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
        data["pool"] = self.pool
        return await handler(event, data)