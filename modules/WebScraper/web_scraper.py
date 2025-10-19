import asyncio
import csv
import json
import os
import random
import re
import logging
import time
from datetime import datetime
from asyncio import Lock
import multiprocessing
import traceback
import dateparser
from config import WEB_SCRAPER_LOG_PATH
from modules.DatabaceSQLiteController.async_sq_lite_connector import AsyncAdvertsDatabase
from modules.MainLogger.logger import setup_logger_from_yaml
from modules.PlayWrightManager.await_manager import PWBrowserManager

from modules.TwoCaptchaSolver.two_captcha_solver import TwoCaptchaService
from modules.WebScraper.utils import extract_email_from_text, extract_numberic_value, extract_phone_numbers_from_text, formated_phone_number
from typess import FiltrOption, JobParams, ScraperStatus

lock = Lock()

class WebScraper:
    def __init__(
        self,
        thread_id: int,
        db_controller: AsyncAdvertsDatabase,
        filtr_params: JobParams,
        site_id: int,
        logger: logging.Logger|None = None,
        log_path: str = WEB_SCRAPER_LOG_PATH,
        start_url: str = "https://www.arbeitsagentur.de",
        work_url: str = None,
        captcha_token:str = None
    ):
        
        self.filtr_params = filtr_params
        self.db_controller = db_controller
        self.start_url = start_url
        self.work_url = work_url if work_url else f"{start_url}/jobsuche/"
        self.url = None  

        self.thread_id = thread_id
        self.browser_manager = PWBrowserManager()
        self.captcha_service = TwoCaptchaService(captcha_token) if captcha_token else None
        self.browser_page = None
        self.browser_page_advert = None
        self.site_id = site_id
        self.logger = logger if logger else setup_logger_from_yaml(log_path=log_path)

        self.adverts_list = None
        self.existing_links = []
        self.is_headless = False
        self.work_status = ScraperStatus.STOPED
        self.session_id = None

        # статистичні дані
        self.max_error_dur = 10 # кількість помилок в зборі оголошень оброблених за невеликий проміжок часу 
        self.error_counts = 0 # загальна кількість помилок
        self.error_dur = 0 # переважаюча кількість помилок підряд
        # Дані про оголошення
        self.total_count_results = 0 # загальна кількість оголошень результаті видачі
        self.advert_count = 0 # загальна кількість оброблених оголошеннь
        self.succes_adverts_count = 0 # кількість успішно оброблених оголошеннь
        self.error_adverts_count = 0 # кількість оголошеннь завершених помилкою
        self.notusable_adverts_count = 0 # кількість не підходящих оголошеннь
        self.existing_count = 0 # кількисть оголошень які повторяються

    async def _initialize_browser(self):
        """Ініціалізує браузер Playwright."""
        return await self.browser_manager.initialize_browser(is_headless=self.is_headless)

    def _extrack_clean_url(self, url:str)->str:
        return url.split('?')[0].strip()

    def _extract_sid_from_url(self, url:str)->str:
        return self._extrack_clean_url(url).split("/")[-1].strip()

    async def start(self, f_params: JobParams = None):
        """Запускає браузер"""
        
        try:
            if self.work_status == ScraperStatus.WORKING:
                print("Парсер вже запущено") 
                return False
            
            if f_params:
                self.filtr_params = f_params
            
            self.work_status = ScraperStatus.WORKING
            self.session_id = datetime.now()

            self.logger.info(f"Thread {self.thread_id}: Starting scraper.")
            await self.get_existing_list_from_BD(1)
            self.url = self.generate_url()
            self.logger.info(f"Generated URL from parameters [start]: {self.url}")
            
            # create tabs
            self.browser_page = await self._initialize_browser()
            self.browser_page_advert = await self.browser_manager.create_new_page()
            
            # return to main tab
            await self.browser_page.bring_to_front()

            # Вхід за URL на сторінку з результатами, за відповідними параметрами
            await self.browser_page.goto(self.url)
            await self.confirm_modal_cookie()

            # Процес оброблення оголошень зі сторінки з результатами
            await self.process_adverts_list()
            # await asyncio.sleep(10000) # TODO del
        except Exception as e:
            self.logger.critical(f"Вспливання помилки в методі [start]: {e}")
            raise Exception(e)

        await self._stop()

    async def _stop(self):
        """Завершує роботу парсера."""
        self.work_status = ScraperStatus.STOPED
        self.logger.info(f"Thread {self.thread_id}: Stopping scraper.")
        if self.browser_page:
            await self.browser_manager.close_browser()
        if self.browser_page_advert:
            await self.browser_page_advert.close()
            self.browser_page_advert = None

    async def set_stop_status(self):
        """Змінюємо статус роботу парсера."""
        self.work_status = ScraperStatus.STOPED

    async def set_advert_to_BD(self, data:dict):
        try:
            await self.db_controller.add_advert(**data)
        except Exception as e:
            self.logger.critical(f"Web Scraper [set_advert_to_BD]. При передачі оголошення в Базу Даних сталася помилка: {e}")
            raise Exception(e)

    async def get_existing_list_from_BD(self, max_old:int = 1) -> None:
        links = []

        if max_old and max_old>0:
            results = await self.db_controller.get_all_adverts(max_old)
            links = [row['link'] for row in results]
        self.existing_links = links

    async def process_select_advert(self, advert_item):
        """
        Обробляє вибране оголошення
        Переходить за посиланням в новій вкладці
        """

        advert_href = await advert_item.get_attribute("href")

        if not advert_href:
            link_element = advert_item.locator("a").first
            if await link_element.count() > 0:
                advert_href = await link_element.get_attribute("href")

        advert_href_clean = self._extrack_clean_url(advert_href)
        if advert_href_clean in self.existing_links: 
            print("Ця вакансія недавно додавалася вже.")
            return #якщо вже є в опрацьованих, завершуємо роботу даного методу 

        await self.browser_page_advert.bring_to_front()
        await self.browser_page_advert.goto(advert_href)
        
        print(f"Advert processing[#{self.advert_count}] : {advert_href}")

        # Перевірка на коректність оголошення
        is_no_iterable = await self.get_visible_element(self.browser_page_advert, "h4:has-text('Vollständige Stellenbeschreibung bei unserem Kooperationspartner einsehen:')", 1000)
        if is_no_iterable : 
            self.notusable_adverts_count += 1 # записуємо про оголошення не коректного типу
            return None

        # вкладені функції
        async def get_phones_list() -> list[str]:
            """
            Отримує список телефонних номерів з відповідних блоків.
            
            Returns:
                list[str]: Список телефонних номерів або порожній список, якщо їх немає.
            """
            # Селектори для пошуку телефонних номерів
            phone_selectors = [
                "#detail-bewerbung-telefon-Telefon",  # Основний номер
                "#detail-bewerbung-telefon-Mobil",  # Мобільний номер
            ]
            
            phones_list = []
            
            # Перевіряємо кожен селектор
            for selector in phone_selectors:
                phone_block = await self.get_visible_element(self.browser_page_advert, selector, timeout=100)
                if phone_block:  # Якщо блок знайдено і видимий
                    phone_text = await self.get_text_from_element(phone_block)
                    if phone_text:  # Перевірка, чи є текст
                        phones_list.append(phone_text)
            
            return phones_list
        
        async def get_type_offer_block_text():
            type_offer_block = await self.get_visible_element(self.browser_page_advert, ".arbeitszeiten", 100)
            
            if not type_offer_block:
                return None

            # Отримуємо всі теги одразу
            type_offer_tags = type_offer_block.locator("span.tag")
            
            # Отримуємо всі тексти тегів у списку за допомогою list comprehension
            tags_list = [await self.get_text_from_element(type_offer_tags.nth(i)) for i in range(await type_offer_tags.count())]
            
            # Об'єднуємо всі теги в рядок
            return ",".join(tags_list) if tags_list else None

        async def get_data_posted(txt:str):
            if txt: 
                time_all = dateparser.parse(str(txt))
                if time_all:
                    formatted_date = time_all.strftime('%Y-%m-%d')
                    return formatted_date
            return None

        # При не відображенні контактної форми, перевіряємо на наявність каптчі і вирішуємо її
        contact_form = await self.get_visible_element(self.browser_page_advert, ".angebotskontakt")
        if not contact_form:
            await self.proc_captcha()

        # Шукаємо елементи з інформацією про оголошення
        main_tels_list = await get_phones_list() # список номерів контактного блоку
        advert_title = await self.get_visible_element(self.browser_page_advert, "#detail-kopfbereich-titel", 100)
        contact_block = await self.get_visible_element(self.browser_page_advert, "#detail-bewerbung-adresse", 100)
        job_title_block = await self.get_visible_element(self.browser_page_advert, "#detail-kopfbereich-hauptberuf", 100)
        time_posted_block = await self.get_visible_element(self.browser_page_advert, "#detail-kopfbereich-veroeffentlichungsdatum", 100)
        mail_block = await self.get_visible_element(self.browser_page_advert, "#detail-bewerbung-mail", 100)
        description_block = await self.get_visible_element(self.browser_page_advert, "#detail-beschreibung-beschreibung", 100)
        address_block = await self.get_visible_element(self.browser_page_advert, "#detail-arbeitsorte-arbeitsort-0", 100)        
        location_block = await self.get_visible_element(self.browser_page_advert, "#detail-kopfbereich-arbeitsort", 100)        
        time_posted_block = await self.get_visible_element(self.browser_page_advert, "#detail-kopfbereich-veroeffentlichungsdatum", 100)  
        employer_company_name_block = await self.get_visible_element(self.browser_page_advert, "#detail-kopfbereich-firma", 100)   

        type_offer_block_text = await get_type_offer_block_text()
        advert_title_text = await self.get_text_from_element(advert_title)
        job_title_block_text = await self.get_text_from_element(job_title_block)
        time_posted_block_text = await self.get_text_from_element(time_posted_block)
        mail_block_text = await self.get_text_from_element(mail_block)
        address_block_text = await self.get_text_from_element(address_block)
        location_block_text = await self.get_text_from_element(location_block)
        time_posted_block_text = await self.get_text_from_element(time_posted_block)
        time_posted_block_date = await get_data_posted(time_posted_block_text)
        employer_company_name_text = await self.get_text_from_element(employer_company_name_block)
        mails_list = extract_email_from_text(await self.get_text_from_element(description_block))
        add_tels_list = extract_phone_numbers_from_text(await self.get_text_from_element(description_block)) # список номерів з опису
        tels_list = [] # фінальний список телефонних номерів зі всієї сторінки
        contact_block_text = await self.get_text_from_element(contact_block)
        employer_contact_person_text = None
        if contact_block_text:
            contact_block_text_lines = contact_block_text.split("\n")

            for line in contact_block_text_lines:
                if 'Frau' in line or 'Herr' in line:
                    employer_contact_person_text = line  # Повертає рядок з ім'ям

        # Обєднання телефонних номерів в один список з перевіркою на валідність
        for tel_item in [*main_tels_list, *add_tels_list]:
            phone_text = tel_item
            formated_phone = formated_phone_number(phone_text)
            if formated_phone: phone_text = formated_phone
            tels_list.append(phone_text)

        # Обєднання з електронних скриньок в один список
        if mail_block_text: mails_list.append(mail_block_text)

        # маневр =)
        try:
            tels_list = list(set(tels_list))
            mails_list = list(set(mails_list))
        except:
            pass

        job_title_block_text = job_title_block_text if job_title_block_text and job_title_block_text.strip() else "unknown"

        adverts_result_dict = {
            "sid" : self._extract_sid_from_url(str(advert_href)),
            "title" : advert_title_text,
            "job_title" : job_title_block_text,
            "address" : address_block_text,
            "location" : location_block_text,
            "type_offer" : type_offer_block_text,
            "posted_date" : time_posted_block_date,
            "posted_date_txt" : time_posted_block_text,
            "employer_company_name" : employer_company_name_text,
            "employer_contact_person" : employer_contact_person_text,
            "email" : ", ".join(mails_list),
            "phone": ", ".join(tels_list),
            "link" : self._extrack_clean_url(advert_href),
            "time_getting" : str(datetime.now().isoformat()),
            "session_id" : self.session_id
        }

        return adverts_result_dict

    async def process_adverts_list(self):
        """
        Обробляє оголошення на сторінці:
        - Завантажує список оголошень.
        - Відправляє на обробку.
        - Видаляє опрацьовані елементи.
        - Підвантажує нові оголошення, при наявності.
        """
        
        total_count_results_locator = self.browser_page.locator("#suchergebnis-h1-anzeige")
        if  await total_count_results_locator.count() > 0:
            total_count_results_locator_txt = await total_count_results_locator.inner_text()
            self.total_count_results = extract_numberic_value(total_count_results_locator_txt)
        else:
            self.logger.error(f"Не вдалося отримати загальну кількість оголошень")
                        
        while True:
            # Переведення в штатному режимі на головну вкладку
            await self.browser_page.bring_to_front()
            # Перевірка на статус роботи парсера
            if not self.work_status == ScraperStatus.WORKING: break

            await self.load_adverts_list()
            adverts_count =  await self.adverts_list.count()
            print("Adverts count: ",adverts_count)
            
            # Перевірка на наявність модального вікна з оголошенням
            is_have_warn_window = await self.is_have_warn_window()
            if is_have_warn_window: 
                self.work_status = ScraperStatus.STOPED
                logging.warning("Отримано помилку з сайту(Внутрішня помилка сервісу, оголошення завершились). Парсер зупинений.")
                break

            if adverts_count > 0:
                advert_i = 0
                while advert_i < adverts_count:
                    self.advert_count += 1 # записуємо про початок обробки оголошення
                    try:
                        # Перевірка на статус роботи парсера
                        if not self.work_status == ScraperStatus.WORKING: break

                        advert_item = self.adverts_list.nth(advert_i)

                        # Пропускаємо непомітні елементи
                        if not await advert_item.is_visible():
                            advert_i += 1
                            continue

                        # Обробка оголошення
                        advert_data = await self.process_select_advert(advert_item)
                        if advert_data:
                            # Передача отриманих даних в БД
                            await self.set_advert_to_BD(advert_data)
                            self.existing_links.append(self._extrack_clean_url(advert_data.get("link", "")))

                        # Видалення опрацьованого оголошення
                        await advert_item.evaluate("(element) => element.parentNode.removeChild(element)")
                        adverts_count -= 1  # Зменшуємо кількість оголошень
                        await self.update_processing_status(True)
                    except Exception as e:
                        advert_i += 1
                        await self.update_processing_status(False)
                        error_message = traceback.format_exc()
                        self.logger.critical(f"Помилка при обробці оголошення. Серія помилок: {self.error_dur} #{self.error_counts}. Деталі: {error_message}")
                        
                        await asyncio.sleep(5000)
            else:
                # За наявності підгружає наступну сторінку з оголошеннями, в іншому випадку завершує цикл
                if not await self.load_more_adverts():
                    self.logger.info(f"Оголошень не залишилося. Перебір результатів завершується.")
                    break

    async def update_processing_status(self, success: bool):
        """
        Оновлює статус обробки оголошень, враховуючи успішність або помилку.

        Args:
            success (bool): Прапорець успішності обробки оголошення.
            error_message (str, optional): Текст помилки, якщо обробка завершилася невдачею.
        """
        if success:
            self.error_dur = max(0, self.error_dur - 1)  # Зменшуємо серію помилок, але не нижче 0
            self.succes_adverts_count += 1 # Додаємо інформацію про успішно оброблене оголошення
        else:
            self.error_counts += 1
            self.error_dur += 1
            self.error_adverts_count += 1 # Додаємо інформацію про оголошення завершене з помилкою

        # Додатковий аналіз
        if self.error_dur >= self.max_error_dur:
            # TODO змінити хід обпрацювання
            self.logger.error("Перевищено допустиму кількість помилок підряд. Зупинка обробки.")
            raise RuntimeError("Зупинка через надмірну кількість помилок.")

    async def load_adverts_list(self):
        """Отримує всі підгружені оголошення"""
        adverts_area = self.browser_page.locator("#ergebnisliste").first
        self.adverts_list = adverts_area.locator(".ergebnisliste-item")

    async def load_more_adverts(self) -> bool: 
        """
        Підвантаження оголошень з пошукового запиту
        :return bool, True - оголошення підвантажено, False - немає більше оголошень 
        """

        btn_id_txt = "ergebnisliste-ladeweitere-button"
        btn_more_locator = self.browser_page.locator(f"#{btn_id_txt}")
        
        if await btn_more_locator.count() > 0:
            btn_more = btn_more_locator.first
            if await btn_more.is_visible(timeout=5000):
                await btn_more.click(force=True)
                await self.browser_page.wait_for_timeout(2000)
                return True
        
        return False

    async def confirm_modal_cookie(self):
        """
        Перевіряє на наявність модального вікна з політикою кондефінційності
        Надає згоду на збереження даних
        """

        modeal_id_name = "#bahf-cookie-disclaimer-modal"
        await self.browser_page.wait_for_selector(modeal_id_name, timeout=10000)
        modal_container = self.browser_page.locator(modeal_id_name)
        
        if await modal_container.count() > 0:
            modal_container = modal_container.first
            # modal_comfirm_btn = modal_container.locator(".modal-footer").locator(".ba-btn-primary")
            modal_comfirm_btn = modal_container.locator('button[data-testid="bahf-cookie-disclaimer-btn-alle"]')
            await modal_comfirm_btn.click(force=True)
            await self.browser_page.wait_for_timeout(2000)

    async def get_visible_element(self, select_page, selector, timeout=2000):
        """
        Шукає і повертає перший едемент за селектором,
        в іншому випадку False
        обмежене очікування
        """
        element_locator = select_page.locator(selector)
        try:
            # Чекаємо, поки елемент стане видимим протягом timeout
            await element_locator.first.wait_for(state="visible", timeout=timeout)
            return element_locator.first
        except Exception:
            # Якщо елемент не з'явився
            return False

    async def get_text_from_element(self, element_locator):
        """
        Отримує текст з елемента, якщо він існує.
        Якщо елемент не знайдений, повертає None.
        """
        if element_locator:
            try:
                return await element_locator.inner_text()  # Отримуємо текст з елемента
            except Exception as e:
                self.logger.error(f"При спробі отримати текст з '{str(element_locator)}' сталася помилка: {str(e)}")
            
        return None

    async def is_have_captcha(self, select_page):
        """
        Шукає і повертає каптчу, в іншому випадку False
        """
        return await self.get_visible_element(select_page, "#captchaForm")

    async def proc_captcha(self):
        """
        При виявленні каптчі, проводить операцію по усуненні її
        """
        captcha_block = await self.is_have_captcha(self.browser_page_advert)
        if captcha_block:
            print("Виявлено каптчу! -------")
            for i in range(3):
                print(f"Проходження каптчі спроба #{i}")
                captcha_image_path = self.browser_page_advert.locator("#kontaktdaten-captcha-image")
                
                if await captcha_image_path.count()>0:
                    captcha_image_path = await captcha_image_path.first.get_attribute("src")

                captcha_result_input = self.browser_page_advert.locator("#kontaktdaten-captcha-input")
                captcha_submit_button_locator = self.browser_page_advert.locator("#kontaktdaten-captcha-absenden-button")

                print("Посилання на зображення каптчі", captcha_image_path)
            
                try:
                    result = await self.captcha_service.solve_text_captcha(captcha_image_path)

                    if await captcha_result_input.count()>0:
                        await captcha_result_input.first.fill(result["code"])
                    if await captcha_submit_button_locator.is_enabled():
                        await captcha_submit_button_locator.click()

                    error_captcha_block = await self.get_visible_element(self.browser_page_advert, "p#kontaktdaten-captcha-input-fehler:has-text('Die von Ihnen eingegebenen Zeichen waren nicht korrekt')", 2000)

                    if error_captcha_block:
                        self.logger.warning(f"Каптча id#{result['captchaId']} НЕ ПРИЙНЯТО!")
                    else:
                        self.logger.info(f"Каптча id#{result['captchaId']} УСПІШНО!")

                    await self.captcha_service.report_result(result['captchaId'], False if error_captcha_block else True)
                    if not error_captcha_block:
                        break
                except Exception as e:
                    self.logger.error(f"Cервіс 2Captcha повернув помилку - {e} .")

                await asyncio.sleep(3)

        else:
            print("Каптчі немає! -------")

    async def is_have_warn_window(self):
        # Пошук елемента за частковим текстом (регістронезалежно)
        partial_text = "Es konnte keine Verbindung zum Server hergestellt werden."
        element = self.browser_page.locator(f"xpath=//*[contains(text(), '{partial_text}')]")

        if await element.count() > 0:
            print("Елемент вспливаючого вікна з помилкою знайдено!")
            text = await element.first.text_content()
            print(f"Текст елемента: {text}")
            return True
        else:
            return False
    
    async def get_captcha_balance(self):
        return await self.captcha_service.get_balance()

    def generate_url(self) -> str:
        """
        Генерує URL для парсингу на основі початкової URL та параметрів фільтру.
        """
        query_params = []

        if self.filtr_params.type_offer:
            query_params.append(f"{FiltrOption.TYPEOFFER.value}={self.filtr_params.type_offer}")
        if self.filtr_params.branch and len(self.filtr_params.branch)>0:
            query_params.append(f"{FiltrOption.BRANCH.value}={";".join(self.filtr_params.branch)}")
        if self.filtr_params.beruf and len(self.filtr_params.beruf)>0:
            query_params.append(f"{FiltrOption.BERUF.value}={";".join(self.filtr_params.beruf)}")
        if self.filtr_params.availability and len(self.filtr_params.availability)>0:
            query_params.append(f"{FiltrOption.AVAILABILITY.value}={";".join(self.filtr_params.availability)}")
        if self.filtr_params.time_slot:
            query_params.append(f"{FiltrOption.PUBLISHED.value}={self.filtr_params.time_slot}")

        return f"{self.work_url}suche?{'&'.join(query_params)}"
    
    