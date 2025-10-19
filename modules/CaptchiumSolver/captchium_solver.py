import random
import time
import traceback

from captchium import Captchium
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class CaptchiumSolver:
    """Модуль для роботи з CAPTCHA для Driverium, Captchium та Selenium"""

    def __init__(self, driver, recognize_service="google"):
        """
        Ініціалізація модуля для роботи з CAPTCHA
        :param driver: Selenium WebDriver
        :param recognize_service: Сервіс для розпізнавання CAPTCHA (за замовчуванням "google")
        """
        self.driver = driver
        self.captchium = Captchium(driver, recognize_service=recognize_service)

        # Xpath для пошуку iframe з reCAPTCHA
        self.reCaptcha_Xpath = '//iframe[@title="reCAPTCHA"]'

    def get_captchium(self):
        """Повертає екземпляр Captchium"""
        return self.captchium
    
    def is_found_captcha(self):
        """
        Метод для пошуку CAPTCHA на сторінці
        """
        return True if self.driver.find_elements(By.XPATH, self.reCaptcha_Xpath) else False
    
    def solve_captcha(self, attempts=10):
        """
        Метод для вирішення CAPTCHA, виконується декілька спроб за задану кількість спроб
        :param attempts: Кількість спроб розв'язання CAPTCHA
        """
        for attempt in range(attempts):
            print(f"CaptchaSolverModule: Спроба #{attempt+1}")

            # Перевірка, чи є reCAPTCHA на сторінці
            if self.driver.find_elements(By.XPATH, self.reCaptcha_Xpath):
                try:
                    # Перемикаємось на iframe з reCAPTCHA
                    recaptcha_frame = self.driver.find_element(By.XPATH, self.reCaptcha_Xpath)
                    self.driver.switch_to.frame(recaptcha_frame)

                    # Клікаємо на чекбокс для початку перевірки reCAPTCHA
                    recaptcha_checkbox = self.driver.find_element(By.ID, "recaptcha-anchor")
                    # recaptcha_checkbox.click()
                    self.driver.execute_script("arguments[0].click();", recaptcha_checkbox)

                    # Повертаємось до основного контенту сторінки
                    self.driver.switch_to.default_content()

                    # Часова затримка перед наступними діями
                    time.sleep(random.uniform(1.6, 4.0))

                    # Перевірка всіх iframe на наявність CAPTCHA
                    # iframe_elements = self.driver.find_elements(By.TAG_NAME, "iframe")
                    iframe_elements = self.driver.find_elements(By.CSS_SELECTOR, 'iframe[title="reCAPTCHA"]')
                    for iframe in iframe_elements:
                        try:
                            self.driver.switch_to.frame(iframe)
                            self.captchium.solve(iframe)
                            return True  # Якщо CAPTCHA вирішено, виходимо з методу
                        except Exception as e:
                            print('Error:', e)

                        # if iframe.find_elements(By.ID, "rc-imageselect"):
                        #     self.driver.switch_to.frame(iframe)
                        #     try:
                        #         self.captchium.solve(iframe)
                        #         return True  # Якщо CAPTCHA вирішено, виходимо з методу
                        #     except Exception as e:
                        #         print('Error:', e)
                        # else:
                        #     print('Тут нема ніхуя')
                        
                        # Перемикаємось на кожен iframe по черзі
                        # self.driver.switch_to.frame(iframe)

                        # # Перевірка на наявність CAPTCHA, якщо є, то вирішуємо її
                        # if self.driver.find_elements(By.ID, "rc-imageselect"):
                        #     self.driver.switch_to.default_content()  # Повертаємось до основного контенту
                            
                        #     # Використовуємо Captchium для розв'язання CAPTCHA
                        #     try:
                        #         self.captchium.solve(iframe)
                        #         return True  # Якщо CAPTCHA вирішено, виходимо з методу
                        #     except Exception as e:
                        #         print('Error:', e)

                    

                except Exception as e:
                    print(f"Помилка під час спроби вирішення CAPTCHA (спроба {attempt + 1}): {e}")
                    print(traceback.format_exc())
                    continue  # Продовжуємо наступну спробу в разі помилки

        print("Не вдалося вирішити CAPTCHA після кількох спроб.")
        return False  # Якщо не вдалося вирішити після заданої кількості спроб

    