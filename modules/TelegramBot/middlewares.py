from aiogram import BaseMiddleware
from aiogram.types import Message
from aiogram.filters import Command

class AdminMiddleware(BaseMiddleware):
    """
    Проміжкова функція для перевірки на адмін права, крім переданих випадків
    :allowed_user_ids - список користувачів з адмін привілегіями
    :exempt_commands - список найменувань команд для винятку
    """
    def __init__(self, allowed_user_ids: list, exempt_commands: list):
        super().__init__()
        self.allowed_user_ids = allowed_user_ids
        self.exempt_commands = exempt_commands

    async def __call__(self, handler, event: Message, data: dict):
        # Перевірка, чи команда в списку винятків
        if event.text and any(Command(command) for command in self.exempt_commands if command in event.text):
            pass
        else:
            user_id_str = str(event.from_user.id)
            if user_id_str not in self.allowed_user_ids:
                await event.answer("Вибачте, але у вас немає доступу до цієї команди.")
                return False
        
        return await handler(event, data)