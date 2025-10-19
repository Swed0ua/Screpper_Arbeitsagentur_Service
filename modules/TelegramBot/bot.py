import asyncio
import sys
import traceback
from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
# from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from config import ALLOWED_USER_IDS, TG_BOT_TOKEN
from modules.TelegramBot.middlewares import AdminMiddleware
from modules.TelegramBot.handlers import procc_callback_handler, register_handlers


# Ініціалізація бота та диспетчера
dp = Dispatcher()
bot = Bot(token=TG_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

# Ініціалізація проміжних функцій
admin_middleware = AdminMiddleware(allowed_user_ids=ALLOWED_USER_IDS, exempt_commands=['id'])
dp.message.middleware(admin_middleware)

# Реєстрація обробників
register_handlers(dp)

@dp.callback_query()
async def main_callback_handler(callback: CallbackQuery, state: FSMContext):
    try:
        await procc_callback_handler(callback, state)
    except Exception as e:
        print(f'[dp.callback_query] Error:', e)

async def start_telegram_bot():
    """
    Функція для запуску Telegram-бота.
    """
    await dp.start_polling(bot)