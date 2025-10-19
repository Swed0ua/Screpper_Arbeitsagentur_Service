import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

from driverium import Driverium
from captchium import Captchium

from captchium_solver import CaptchiumSolver

class WebDriverManager:
    """Клас для управління WebDriver"""

    def __init__(self, headless=True):
        """Ініціалізація WebDriver"""
        self.headless = headless
        self.driver = None

    def create_driver(self):
        """Створення WebDriver з опціями"""
        options = Options()
        options.headless = self.headless
        service = Service(Driverium().get_driver())
        self.driver = webdriver.Chrome(service=service, options=options)
        return self.driver

    def quit_driver(self):
        """Закриття WebDriver"""
        if self.driver:
            self.driver.quit()
            self.driver = None

class CaptchaSolverModule:
    """Модуль для роботи з CAPTCHA та Selenium"""

    def __init__(self, driver_manager):
        self.driver_manager = driver_manager
        self.captcha_solver = None

    def interact_with_captcha(self, url):
        """Метод для взаємодії з CAPTCHA на сторінці"""
        driver = self.driver_manager.create_driver()
        self.captcha_solver = CaptchiumSolver(driver)
        
        driver.get(url)
        
        try:
            is_found_captcha = self.captcha_solver.is_found_captcha()
            if is_found_captcha:
                print("Каптча знайдена. Працюємо над вирішенням...")
                result = self.captcha_solver.solve_captcha()
                print("=) Каптча пройдена" if result else "=( Каптчу не вдалося обійти")
            else:
                print("Каптча не знайдена")

            time.sleep(100)

        except Exception as e:
            print(f"Помилка при взаємодії з CAPTCHA: {e}")
        finally:
            driver.quit()


# Основна частина для тестування
if __name__ == "__main__":

    # Створюємо об'єкти для управління браузером
    driver_manager = WebDriverManager(headless=False)

    # URL сторінки з CAPTCHA
    url = "https://www.google.com/recaptcha/api2/demo"

    captcha_solver_module = CaptchaSolverModule(driver_manager=driver_manager)
    captcha_solver_module.interact_with_captcha(url)


# Воно регає автоматичні запити для аудіофайлів