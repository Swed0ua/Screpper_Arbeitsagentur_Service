import os
import sys
from twocaptcha import TwoCaptcha

class TwoCaptchaService:
    def __init__(self, api_key: str = None):
        """
        Ініціалізація сервісу для роботи з 2Captcha.
        :param api_key: API-ключ для доступу до 2Captcha.
        """
        self.api_key = api_key or os.getenv('APIKEY_2CAPTCHA', 'YOUR_API_KEY')
        self.solver = TwoCaptcha(self.api_key)

    def get_balance(self):
        """
        Отримує доступний баланс користувача.
        :return: Баланс у вигляді рядка з сумою.
        :raises Exception: Якщо виникає помилка при запиті балансу.
        """
        try:
            balance = self.solver.balance()
            return f"Баланс: {balance} USD"
        except Exception as e:
            raise Exception(f"Помилка отримання балансу: {e}")

    def solve_text_captcha(self, image_path: str):
        """
        Вирішує текстову капчу.
        :param image_path: Шлях до зображення з капчею.
        :return: Результат вирішення капчі.
        :raises Exception: Якщо виникає помилка при вирішенні капчі.
        """
        try:
            result = self.solver.normal(image_path)
            return result
        except Exception as e:
            raise Exception(f"Помилка вирішення капчі: {e}")

    def report_result(self, id:str, is_correct:bool):
        """
        Метод надсилає сервісу дані про коректність результату
        """
        try:
            self.solver.report(id, is_correct)
        except Exception as e:
            raise Exception(f"Помилка вирішення капчі: {e}")
    

if __name__ == "__main__":
    # Ініціалізація сервісу
    api_key = 'efb2165014296eb6417e4c9284e1187f'  # Замініть на ваш API-ключ
    captcha_service = TwoCaptchaService(api_key)

    # Отримання балансу
    try:
        balance = captcha_service.get_balance()
        print(balance)
    except Exception as e:
        print(e)

    # captcha_image_path = 'https://rest.arbeitsagentur.de/idaas/id-aas-service/ct/v1/captcha/2016332B-8EAF-4DED-A051-B077671BE300?type=image&languageIso639Code=de'  # Замініть на шлях до вашого зображення
    # try:
    #     result = captcha_service.solve_text_captcha(captcha_image_path)
    #     print(f"Капча вирішена: {result}")
    # except Exception as e:
    #     print(e)
