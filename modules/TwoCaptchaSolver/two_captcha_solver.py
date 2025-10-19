import os
import asyncio
from twocaptcha import TwoCaptcha
from concurrent.futures import ThreadPoolExecutor

class TwoCaptchaService:
    def __init__(self, api_key: str = None):
        """
        Ініціалізація сервісу для роботи з 2Captcha.
        :param api_key: API-ключ для доступу до 2Captcha.
        """
        self.api_key = api_key or os.getenv('APIKEY_2CAPTCHA', 'YOUR_API_KEY')
        self.solver = TwoCaptcha(self.api_key)
        self.executor = ThreadPoolExecutor()
        self.error_captcha_solver = 0
        self.captcha_solver_count = 0

    async def get_balance(self):
        """
        Отримує доступний баланс користувача.
        :return: Баланс у вигляді рядка з сумою.
        :raises Exception: Якщо виникає помилка при запиті балансу.
        """
        loop = asyncio.get_event_loop()
        try:
            balance = await loop.run_in_executor(self.executor, self.solver.balance)
            return f"Баланс: {balance} USD"
        except Exception as e:
            raise Exception(f"Помилка отримання балансу: {e}")

    async def solve_text_captcha(self, image_path: str):
        """
        Вирішує текстову капчу.
        :param image_path: Шлях до зображення з капчею.
        :return: Результат вирішення капчі.
        :raises Exception: Якщо виникає помилка при вирішенні капчі.
        """
        loop = asyncio.get_event_loop()
        try:
            self.captcha_solver_count += 1 
            result = await loop.run_in_executor(self.executor, self.solver.normal, image_path)
            return result
        except Exception as e:
            print(f"Помилка вирішення капчі: {e}")
            self.error_captcha_solver += 1 
            raise Exception(f"Помилка вирішення капчі: {e}")
            # TODO зробити оголошення.

    async def report_result(self, id: str, is_correct: bool):
        """
        Метод надсилає сервісу дані про коректність результату
        """
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(self.executor, self.solver.report, id, is_correct)
        except Exception as e:
            raise Exception(f"Помилка повідомлення результату: {e}")


async def main():
    # Ініціалізація сервісу
    api_key = 'efb2165014296eb6417e4c9284e1187f'  # Замініть на ваш API-ключ
    captcha_service = TwoCaptchaService(api_key)

    # Отримання балансу
    try:
        balance = await captcha_service.get_balance()
        print(balance)
    except Exception as e:
        print(e)

    # captcha_image_path = 'https://rest.arbeitsagentur.de/idaas/id-aas-service/ct/v1/captcha/2016332B-8EAF-4DED-A051-B077671BE300?type=image&languageIso639Code=de'  # Замініть на шлях до вашого зображення
    # try:
    #     result = await captcha_service.solve_text_captcha(captcha_image_path)
    #     print(f"Капча вирішена: {result}")
    # except Exception as e:
    #     print(e)

# Запуск асинхронної програми
if __name__ == "__main__":
    asyncio.run(main())
