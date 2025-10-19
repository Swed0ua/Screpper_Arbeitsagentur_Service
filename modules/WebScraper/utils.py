import re
import phonenumbers
from phonenumbers import PhoneNumberFormat

def extract_numberic_value(text: str) -> int:
    """
    Витягує перше числове значення з тексту, незалежно від його розташування.

    Args:
        text (str): Вхідний текст, наприклад, '10 Jobs' або 'No jobs found'.
    
    Returns:
        int: Перше знайдене число або 0, якщо числа немає.
    """
    match = re.search(r'\d+', str(text)) 
    return int(match.group()) if match else 0

def extract_email_from_text(text: str | None) -> list:
    """
    Витягує всі адреси електронних пошт з тексту.
    :return - повертає список
    """
    email_pattern = re.compile(
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    )
    emails_lsit = email_pattern.findall(str(text))
    return emails_lsit

def extract_phone_numbers_from_text(text: str | None) -> list:
    """
    Витягує всі міжнародні номери телефонів з тексту.
    :param text: Текст, який містить номери.
    :return: Список міжнародних номерів телефонів.
    """
    if not text:
        return []

    phone_pattern = re.compile(
        r'\+?[1-9]\d{0,3}(?:[ \-\(\)]*\d){7,14}'  # Коректно враховує форматування
    )
    phone_numbers_list = phone_pattern.findall(text)
    # Очищення від зайвих символів, таких як пробіли, дужки тощо
    cleaned_numbers = [re.sub(r'[^\d+]', '', number) for number in phone_numbers_list]
    return cleaned_numbers

def formated_phone_number(text:str) -> str|None:
    """
    Форматує номер телефону
    :return - повертає відформатований номер, або None
    """
    try:
        x = phonenumbers.parse(str(text) , None)
        formatted_number = phonenumbers.format_number(x, PhoneNumberFormat.INTERNATIONAL)
        return formatted_number
    except phonenumbers.NumberParseException:
        return None