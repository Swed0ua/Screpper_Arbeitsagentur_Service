import aiosqlite
import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from config import SQL_LITE_LOG_PATH
from modules.MainLogger.logger import setup_logger_from_yaml

# Налаштування логування
log_path = SQL_LITE_LOG_PATH
logger_t = setup_logger_from_yaml(log_path=log_path)

class AsyncSQLiteConnector:
    """
    Асинхронний клас для роботи з SQLite базою даних.
    """
    
    def __init__(self, file_name: str):
        """
        Ініціалізація AsyncSQLiteConnector.
        :param file_name: назва файлу бази даних
        """
        self.file_name = file_name
        self.lock = asyncio.Lock()
        self.connection = None

    async def connect(self):
        """
        Встановлює підключення до SQLite бази даних.
        """
        try:
            self.connection = await aiosqlite.connect(f"{self.file_name}.db")
            self.connection.row_factory = aiosqlite.Row
            logger_t.info("Асинхронне підключення до SQLite бази даних встановлено.")
        except Exception as err:
            logger_t.error(f"Помилка підключення до бази даних: {err}")
            raise Exception(err)

    async def disconnect(self):
        """
        Закриває підключення до бази даних.
        """
        if self.connection:
            await self.connection.close()
            logger_t.info("Підключення до SQLite бази даних закрито.")

    async def execute_query(self, query: str, params: Optional[tuple] = None):
        """
        Виконує запит до бази даних (без повернення результату).
        """
        async with self.lock:
            try:
                async with self.connection.execute(query, params or ()) as cursor:
                    await self.connection.commit()
            except Exception as err:
                logger_t.error(f"Помилка виконання запиту: {err}")
                await self.connection.rollback()

    async def fetch_all(self, query: str, params: Optional[tuple] = None) -> List[Dict]:
        """
        Виконує запит та повертає всі результати.
        """
        async with self.lock:
            try:
                async with self.connection.execute(query, params or ()) as cursor:
                    rows = await cursor.fetchall()
                    results = [dict(row) for row in rows]
                    print(f"Отримано {len(results)} результатів.")
                    return results
            except Exception as err:
                logger_t.error(f"Помилка виконання запиту: {err}")
                return []

    async def fetch_one(self, query: str, params: Optional[tuple] = None) -> Optional[dict]:
        """
        Виконує запит та повертає перший результат.
        :param query: SQL-запит
        :param params: Параметри для запиту
        :return: Результат у вигляді словника або None
        """
        async with self.lock:
            async with self.connection.execute(query, params or ()) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
        
class AsyncAdvertsDatabase:
    """
    Асинхронний клас для роботи з оголошеннями у SQLite базі даних.
    """

    def __init__(self, db_connector: AsyncSQLiteConnector, database_table:str):
        self.db_connector = db_connector
        self.database_table = database_table

    async def table_check(self):
        """
        Перевіряє на існування таблиці, при негативному результаті створює її
        """
        if not await self.table_exists(self.database_table):
            await self.create_table(self.database_table)
            logger_t.info(f"Таблиця {self.database_table} успішно створена.")
        else:
            logger_t.info(f"Таблиця {self.database_table} вже існує.")

    async def table_exists(self, table_name: str) -> bool:
        """
        Перевіряє, чи існує таблиця з заданою назвою.
        :param table_name: Назва таблиці
        :return: True, якщо таблиця існує, інакше False
        """
        query = """
        SELECT name 
        FROM sqlite_master 
        WHERE type='table' AND name=?;
        """
        result = await self.db_connector.fetch_one(query, (table_name,))
        return result is not None

    async def create_table(self, table_name:str):
        """
        Створює таблицю для збереження контактів.
        """
        query = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sid TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            job_title TEXT NOT NULL,
            address TEXT,
            location TEXT,
            type_offer TEXT,
            posted_date DATE,
            posted_date_txt TEXT,
            employer_company_name TEXT,
            employer_contact_person TEXT,
            email TEXT,
            phone TEXT,
            link TEXT NOT NULL,
            time_getting DATETIME NOT NULL,
            session_id INTEGER
        )
        """
        await self.db_connector.execute_query(query)

    async def add_advert(self, sid:str, link:str, time_getting:str, title: str, job_title:str, address:Optional[str] = None, location:Optional[str] = None, type_offer:Optional[str] = None, posted_date:Optional[str] = None, posted_date_txt:Optional[str] = None, employer_company_name:Optional[str] = None, employer_contact_person:Optional[str] = None, email:Optional[str] = None, phone:Optional[str] = None, session_id:Optional[int] = None):
        try:
            query = f"INSERT OR REPLACE INTO {self.database_table} (sid, title, job_title, address, location, type_offer, posted_date, posted_date_txt, employer_company_name, employer_contact_person, email, phone, link, time_getting, session_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            await self.db_connector.execute_query(query, (sid, title, job_title, address, location, type_offer, posted_date, posted_date_txt, employer_company_name, employer_contact_person, email, phone, link, time_getting, session_id))
            print(f"Оголошення {title} успішно додано.")
        except Exception as e:
            logger_t.error(f"Помилка при додаванні оголошення `{title}`: {e}.")
            raise Exception(e)

    async def get_all_adverts(self, max_old: int = False, session_id: str = None) -> List[Dict]:
        """ 
        Отримує всі оголошення, з можливою фільтрацією за часом та session_id.
        
        :param max_old: Максимальний вік записів у днях (опціонально).
        :param session_id: Фільтрація за session_id (опціонально).
        :return: Список оголошень, які відповідають критеріям.
        """
        query = f"SELECT * FROM {self.database_table}"
        conditions = []

        if max_old:
            conditions.append(f"time_getting > datetime('now', '-{max_old} day{"s" if max_old > 1 else ""}')")

        if session_id:
            conditions.append(f"session_id = '{session_id}'")
        
        # Додаємо умови в запит, якщо вони є
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        return await self.db_connector.fetch_all(query)

    async def delete_advert(self, contact_id: int):
        query = f"DELETE FROM {self.database_table} WHERE id = ?"
        await self.db_connector.execute_query(query, (contact_id,))
        print(f"Оголошення з ID {contact_id} видалено.")

class EmailDatabase:
    """
    Асинхронний клас для роботи з відправленими email в SQLite базі даних.
    """
    
    def __init__(self, db_connector: AsyncSQLiteConnector):
        self.db_connector = db_connector
        self.table_name = "sent_emails"
    
    async def init_table(self):
        """Створює таблицю для збереження відправлених email якщо її немає."""
        query = f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            email TEXT PRIMARY KEY,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            company_name TEXT,
            job_title TEXT
        )
        """
        await self.db_connector.execute_query(query)
        logger_t.info(f"Таблиця {self.table_name} готова.")
    
    async def get_last_sent_date(self, email: str) -> Optional[datetime]:
        """Отримує дату останньої відправки на email."""
        query = f"SELECT sent_at FROM {self.table_name} WHERE email = ?"
        result = await self.db_connector.fetch_one(query, (email,))
        if result and result.get('sent_at'):
            try:
                # Парсити timestamp з SQLite
                sent_at_str = result['sent_at']
                if isinstance(sent_at_str, str):
                    # SQLite зберігає як 'YYYY-MM-DD HH:MM:SS'
                    return datetime.strptime(sent_at_str, '%Y-%m-%d %H:%M:%S')
                return datetime.fromisoformat(sent_at_str)
            except Exception as e:
                logger_t.error(f"Помилка парсингу дати: {e}")
                return None
        return None
    
    async def can_send_email(self, email: str) -> bool:
        """
        Перевіряє чи можна відправляти email (чи пройшло 3+ місяці з останньої відправки).
        
        Returns:
            True якщо можна відправляти (ніколи не відправляли або пройшло 3+ місяці)
            False якщо не можна (відправляли менше 3 місяців тому)
        """
        if not email or not email.strip():
            return True  # Якщо email порожній - можна обробляти
        
        last_sent = await self.get_last_sent_date(email)
        if not last_sent:
            return True  # Ніколи не відправляли - можна
        
        three_months_ago = datetime.now() - timedelta(days=90)
        can_send = last_sent < three_months_ago
        
        if not can_send:
            days_passed = (datetime.now() - last_sent).days
            logger_t.info(f"Email {email} відправлявся {days_passed} днів тому. Потрібно чекати ще {90 - days_passed} днів.")
        
        return can_send
    
    async def record_sent_email(self, email: str, company_name: str = '', job_title: str = ''):
        """Записує email після відправки."""
        if not email or not email.strip():
            return
        
        query = f"""
        INSERT OR REPLACE INTO {self.table_name} (email, sent_at, company_name, job_title)
        VALUES (?, CURRENT_TIMESTAMP, ?, ?)
        """
        await self.db_connector.execute_query(query, (email.strip(), company_name, job_title))
        logger_t.info(f"Записано відправлений email: {email} для {company_name}")

# Приклад використання
async def main_db():
    db = AsyncSQLiteConnector(f"test_db")
    await db.connect()
    db_controller = AsyncAdvertsDatabase(db, database_table="adverts")
    await db_controller.table_check()

    await db.disconnect()
