import asyncio

from initial import DBHandler
from modules.DatabaceSQLiteController.async_sq_lite_connector import main_db
from modules.TelegramBot.bot import start_telegram_bot

asyncio.run(start_telegram_bot())


    