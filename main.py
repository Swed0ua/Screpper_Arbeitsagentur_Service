import asyncio
import logging
import sys
import traceback

from config import CAPTCHA_SLOLVER_TOKEN, DB_PATH, MySQLConfig
from initial import DBHandler, WebScraperHandler
from modules.DatabaceSQLiteController.async_sq_lite_connector import AsyncAdvertsDatabase, AsyncSQLiteConnector
from modules.MainLogger.logger import get_loger
from modules.TelegramBot.bot import start_telegram_bot
from modules.WebScraper.web_scraper import WebScraper
from typess import Availability, JobParams, TimeSlot

logger_main = get_loger()

async def main():
    try:
        # Підключення до Бази даних
        db_controller = await DBHandler.get_instance()
        await db_controller.table_check()
        # оголошення парсера
        scraper = await WebScraperHandler.init_scraper_instance(db_controller)

        # Запуск TG бота
        await start_telegram_bot()
        
    except Exception as e:
        error_message = traceback.format_exc()
        logger_main.critical(f'Помилка в головній функції(main), {error_message}')
    finally:
        await WebScraperHandler.close_scraper()
        await DBHandler.disconnect_from_BD()
            

if __name__ == "__main__":
    asyncio.run(main())
