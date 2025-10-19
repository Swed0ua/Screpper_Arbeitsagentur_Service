import sqlite3
import logging
from typing import List, Dict, Optional

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SQLiteConnector:
    """
    Клас для роботи з SQLite базою даних.
    """

    def __init__(self, file_name: str):
        """
        Ініціалізація SQLiteConnector.
        :param file_name: назва файлу бази даних
        """
        self.file_name = file_name
        self.connection = None
        self.cursor = None

    def connect(self):
        """
        Встановлює підключення до SQLite бази даних.
        """
        try:
            self.connection = sqlite3.connect(f"{self.file_name}.db")
            self.connection.row_factory = sqlite3.Row
            self.cursor = self.connection.cursor()
            logger.info("Підключення до SQLite бази даних встановлено.")
        except sqlite3.Error as err:
            logger.error(f"Помилка підключення до бази даних: {err}")
            raise

    def disconnect(self):
        """
        Закриває підключення до бази даних.
        """
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        logger.info("Підключення до SQLite бази даних закрито.")

    def execute_query(self, query: str, params: Optional[tuple] = None):
        """
        Виконує запит до бази даних (без повернення результату).
        """
        try:
            self.cursor.execute(query, params or ())
            self.connection.commit()
            logger.info(f"Запит успішно виконано: {query}")
        except sqlite3.Error as err:
            logger.error(f"Помилка виконання запиту: {err}")
            self.connection.rollback()

    def fetch_all(self, query: str, params: Optional[tuple] = None) -> List[Dict]:
        """
        Виконує запит та повертає всі результати.
        """
        try:
            self.cursor.execute(query, params or ())
            results = [dict(row) for row in self.cursor.fetchall()]
            logger.info(f"Отримано {len(results)} результатів.")
            return results
        except sqlite3.Error as err:
            logger.error(f"Помилка виконання запиту: {err}")
            return []

class AdvertsDatabase:
    """
    Клас для роботи з оголошеннями у SQLite базі даних.
    """

    def __init__(self, db_connector: SQLiteConnector):
        self.db_connector = db_connector

    def create_table(self):
        """
        Створює таблицю для збереження контактів.
        """
        query = """
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT
        )
        """
        self.db_connector.execute_query(query)

    def add_contact(self, name: str, phone: str, email: Optional[str] = None):
        query = "INSERT INTO contacts (name, phone, email) VALUES (?, ?, ?)"
        self.db_connector.execute_query(query, (name, phone, email))
        logger.info(f"Контакт {name} успішно додано.")

    def get_all_contacts(self) -> List[Dict]:
        query = "SELECT * FROM contacts"
        return self.db_connector.fetch_all(query)

    def delete_contact(self, contact_id: int):
        query = "DELETE FROM contacts WHERE id = ?"
        self.db_connector.execute_query(query, (contact_id,))
        logger.info(f"Контакт з ID {contact_id} видалено.")

# Приклад використання
if __name__ == "__main__":
    db = SQLiteConnector("contacts_db")
    db.connect()

    contacts = AdvertsDatabase(db)
    contacts.create_table()
    contacts.add_contact("John Doe", "1234567890", "john@example.com")

    all_contacts = contacts.get_all_contacts()
    logger.info(f"Усі контакти: {all_contacts}")

    # if all_contacts:
    #     contacts.delete_contact(all_contacts[0]["id"])

    db.disconnect()
