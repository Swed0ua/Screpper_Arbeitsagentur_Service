from config import CAPTCHA_SLOLVER_TOKEN, DB_PATH
from modules.DatabaceSQLiteController.async_sq_lite_connector import AsyncAdvertsDatabase, AsyncSQLiteConnector
from modules.WebScraper.web_scraper import WebScraper
from typess import JobParams, TimeSlot


class DBHandler:
    """
    Клас для керування доступом до єдиного екземпляра бази даних (синглтон).
    """
    __db_connector = None
    __db_controller_instance = None
    __db_table_name = "adverts"
    __db_path = f"{DB_PATH}/arbeitsagentur_db"

    @classmethod
    async def _create_db_instance(self, db_path: str):
        """
        Приватний метод для створення екземпляра бази даних.

        Це ізолює логіку ініціалізації, щоб її можна було легко модифікувати.
        """
        db_connector = AsyncSQLiteConnector(db_path)
        await db_connector.connect()
        instance = AsyncAdvertsDatabase(db_connector, database_table=self.__db_table_name)
        await instance.table_check()
        return instance, db_connector

    @classmethod
    async def get_instance(self):
        """
        Повертає спільний екземпляр db_controller. Якщо екземпляра ще немає, створює його.

        :param db_path: Шлях до файлу бази даних.
        :return: Екземпляр AsyncAdvertsDatabase.
        """
        if self.__db_controller_instance is None:
            db_instance, db_connector = await self._create_db_instance(self.__db_path)
            self.__db_controller_instance = db_instance
            self.__db_connector = db_connector

        return self.__db_controller_instance
    
    @classmethod
    async def disconnect_from_BD(self):
        """
        Закриває зєднання з базою даних
        """
        if self.__db_connector:
            await self.__db_connector.disconnect()
            self.__db_connector = None
            self.__db_controller_instance = None


class WebScraperHandler:
    """
    Клас для керування доступом до єдиного екземпляра парсером (синглтон).
    """
    __scraper = None
    __job_params = JobParams(branch="23", time_slot=TimeSlot.TODAY)

    @classmethod
    async def init_scraper_instance(self, db_controller):
        """
        Приватний метод для створення екземпляра бази даних.

        Це ізолює логіку ініціалізації, щоб її можна було легко модифікувати.
        """
        if not self.__scraper:
            self.__scraper = WebScraper(
                thread_id=1,
                db_controller=db_controller,
                filtr_params=self.__job_params,
                site_id=1,
                captcha_token=CAPTCHA_SLOLVER_TOKEN
            )
        return self.__scraper
    
    @classmethod
    async def set_job_params(self, job_params:JobParams):
        self.__job_params = job_params

    @classmethod
    async def start_scraper(self):
        if self.__scraper:
            await self.__scraper.start()
        else:
            return False
    
    @classmethod
    async def close_scraper(self):
        if self.__scraper:
            await self.__scraper._stop()
            self.__scraper = None
        else:
            return False
        
    @classmethod
    async def stop_scraper(self):
        if self.__scraper:
            await self.__scraper.set_stop_status()
            self.__scraper = None
        else:
            return False