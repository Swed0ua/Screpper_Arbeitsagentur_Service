import mysql.connector
import logging
from typing import List, Dict, Optional

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseConnector:
    """
    Клас для підключення до MySQL бази даних та виконання запитів.
    """

    def __init__(self, host: str, user: str, password: str, database: str):
        """
        Ініціалізація класу DatabaseConnector.
        :param host: хост для підключення
        :param user: користувач
        :param password: пароль
        :param database: назва бази даних
        """
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.connection = None
        self.cursor = None

    def connect(self):
        """
        Встановлює підключення до бази даних.
        """
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database
            )
            self.cursor = self.connection.cursor(dictionary=True)
            logger.info("Підключення до бази даних встановлено.")
        except mysql.connector.Error as err:
            logger.error(f"Помилка підключення: {err}")
            raise

    def disconnect(self):
        """
        Закриває підключення до бази даних.
        """
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        logger.info("Підключення до бази даних закрито.")

    def execute_query(self, query: str, params: Optional[tuple] = None) -> None:
        """
        Виконує запит до бази даних (без повернення результату).
        :param query: SQL запит
        :param params: параметри для запиту (якщо є)
        """
        try:
            self.cursor.execute(query, params)
            self.connection.commit()
            logger.info(f"Запит успішно виконано: {query}")
        except mysql.connector.Error as err:
            logger.error(f"Помилка виконання запиту: {err}")
            self.connection.rollback()

    def fetch_all(self, query: str, params: Optional[tuple] = None) -> List[Dict]:
        """
        Виконує запит та повертає всі результати.
        :param query: SQL запит
        :param params: параметри для запиту (якщо є)
        :return: список результатів запиту
        """
        try:
            self.cursor.execute(query, params)
            results = self.cursor.fetchall()
            logger.info(f"Запит успішно виконано. Кількість результатів: {len(results)}")
            return results
        except mysql.connector.Error as err:
            logger.error(f"Помилка виконання запиту: {err}")
            return []

class ContactDatabase:
    """
    Клас для роботи з контактами у базі даних.
    """

    def __init__(self, db_connector: DatabaseConnector):
        """
        Ініціалізація класу ContactDatabase.
        :param db_connector: об'єкт класу DatabaseConnector
        """
        self.db_connector = db_connector

    def add_contact(self, name: str, phone: str, email: Optional[str] = None) -> None:
        """
        Додає новий контакт до бази даних.
        :param name: ім'я контакту
        :param phone: телефон
        :param email: електронна пошта (не обов'язково)
        """
        query = """
        INSERT INTO contacts (name, phone, email)
        VALUES (%s, %s, %s)
        """
        self.db_connector.execute_query(query, (name, phone, email))
        logger.info(f"Контакт {name} успішно додано.")

    def get_all_contacts(self) -> List[Dict]:
        """
        Отримує всі контакти з бази даних.
        :return: список контактів
        """
        query = "SELECT id, name, phone, email FROM contacts"
        return self.db_connector.fetch_all(query)

    def get_contact_by_id(self, contact_id: int) -> Optional[Dict]:
        """
        Отримує контакт за його ID.
        :param contact_id: ID контакту
        :return: контакт або None
        """
        query = "SELECT id, name, phone, email FROM contacts WHERE id = %s"
        result = self.db_connector.fetch_all(query, (contact_id,))
        return result[0] if result else None

    def update_contact(self, contact_id: int, name: Optional[str] = None, phone: Optional[str] = None, email: Optional[str] = None) -> None:
        """
        Оновлює інформацію про контакт.
        :param contact_id: ID контакту
        :param name: нове ім'я (не обов'язково)
        :param phone: новий телефон (не обов'язково)
        :param email: нова електронна пошта (не обов'язково)
        """
        query = "UPDATE contacts SET name = %s, phone = %s, email = %s WHERE id = %s"
        self.db_connector.execute_query(query, (name, phone, email, contact_id))
        logger.info(f"Контакт з ID {contact_id} успішно оновлено.")

    def delete_contact(self, contact_id: int) -> None:
        """
        Видаляє контакт з бази даних.
        :param contact_id: ID контакту
        """
        query = "DELETE FROM contacts WHERE id = %s"
        self.db_connector.execute_query(query, (contact_id,))
        logger.info(f"Контакт з ID {contact_id} успішно видалено.")

# Приклад використання

if __name__ == "__main__":
    # Налаштування підключення до БД
    db_connector = DatabaseConnector(host="localhost", user="root", password="password", database="contacts_db")
    db_connector.connect()

    # Операції з контактами
    contact_db = ContactDatabase(db_connector)
    contact_db.add_contact(name="John Doe", phone="123-456-7890", email="john.doe@example.com")
    all_contacts = contact_db.get_all_contacts()
    logger.info(f"Усі контакти: {all_contacts}")
    
    # Оновлення контакту
    if all_contacts:
        contact_db.update_contact(all_contacts[0]['id'], name="Johnathan Doe")
    
    # Видалення контакту
    if all_contacts:
        contact_db.delete_contact(all_contacts[0]['id'])

    # Закриття підключення
    db_connector.disconnect()
