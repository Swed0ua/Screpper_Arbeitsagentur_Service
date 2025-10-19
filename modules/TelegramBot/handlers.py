import asyncio
import csv
import os
from typing import List
from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram import types
from aiogram.enums import ParseMode
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext

from initial import DBHandler, WebScraperHandler
from modules.TelegramBot.dt import AVAIL_DICT, BERUF_DICT, BRANCH_DICT, TIME_DICT
from typess import FiltrOption, JobParams, ScraperStatus

scraper_lock = asyncio.Lock()

# Додаткові класи ддля роботи з ботом
class BotServices:
    def __init__(self):
        self.scraper = None
        self.db_controller = None
    
        self.job_params:JobParams = JobParams()

    async def initialize(self):
        if not self.scraper or not self.db_controller:
            self.db_controller = await DBHandler.get_instance()
            self.scraper = await WebScraperHandler.init_scraper_instance(self.db_controller)
        return self.scraper, self.db_controller

services = BotServices()

async def launch_handler(message: Message):
    await message.answer("Парсер підготовлюється до запуску. Очікуйте!", parse_mode=ParseMode.HTML)

    scraper, _ = await services.initialize()
    print(services.job_params)
    await scraper.start(services.job_params)

    await message.answer("Парсер завершив роботу.", parse_mode=ParseMode.HTML)
    await create_and_send_csv(message, session_id=scraper.session_id)

async def stop_handler(message: Message, is_new_mess:bool=True):
    scraper, _ = await services.initialize()
    await scraper.set_stop_status()
    await message.answer("Очікуйте завершення програми....", parse_mode=ParseMode.HTML)

async def get_id_handler(message: Message, is_new_mess:bool=True):
    await message.answer(f"Ваш ID: <a>{message.from_user.id}</a>", parse_mode=ParseMode.HTML)

async def result_menu_handler(message: Message, is_new_mess:bool=True):
    scraper, _ = await services.initialize()
    keyboard = InlineKeyboardMarkup(
    row_width=2,
    inline_keyboard=[
            [InlineKeyboardButton(text="Отримати звіт за сьогодні", callback_data=f"res_1")],
            [InlineKeyboardButton(text="Отримати звіт за 3 дні", callback_data=f"res_3")],
            [InlineKeyboardButton(text="Отримати звіт за тиждень", callback_data=f"res_7")],
            [InlineKeyboardButton(text="Отримати звіт за місяць", callback_data=f"res_31")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"mainMenu")]  
        ])
    
    txt = f"Отримуйте вигрузку оголошень в csv:\n\nПарсер: <i>{"В роботі." if services.scraper.work_status == ScraperStatus.WORKING else "Не працює."}</i> \nОтримано успішних оголошень за останню ітерацію: <i>{services.scraper.succes_adverts_count}</i>"

    if is_new_mess:
        await message.answer(txt, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    else:
        await message.edit_text(txt, parse_mode=ParseMode.HTML, reply_markup=keyboard)

async def main_menu_handler(message: Message, is_new_mess:bool=True):
    keyboard = InlineKeyboardMarkup(
    row_width=2,
    inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Пошук вакансій", callback_data=f"searchVcn")],
            [InlineKeyboardButton(text="⚙️ Налаштування фільтрів", callback_data=f"scraperFiltrs")],
            [InlineKeyboardButton(text="📥 Завантажити результати", callback_data=f"downloadResultMenu")],
            [InlineKeyboardButton(text="🧾 Баланс сервісу 2Captcha", callback_data=f"getCaptchaBalance")]
        ])
    
    if is_new_mess:
        await message.answer(f"Ласкаво просимо до бота пошуку вакансій! Оберіть дію:", parse_mode=ParseMode.HTML, reply_markup=keyboard)
    else:
        await message.edit_text(f"Ласкаво просимо до бота пошуку вакансій! Оберіть дію:", parse_mode=ParseMode.HTML, reply_markup=keyboard)

# Filtrs
async def filtr_menu_handler(message: Message, is_new_mess:bool=True):
    keyboard = InlineKeyboardMarkup(
    row_width=2,
    inline_keyboard=[
            [InlineKeyboardButton(text="📅 Період розміщення", callback_data=f"filtr_{FiltrOption.PUBLISHED.value}")],
            [InlineKeyboardButton(text="🕒 Тип зайнятості", callback_data=f"filtr_{FiltrOption.AVAILABILITY.value}")],
            [InlineKeyboardButton(text="🏢 Галузь", callback_data=f"filtr_{FiltrOption.BRANCH.value}")],
            [InlineKeyboardButton(text="👩‍💼 Професія", callback_data=f"filtr_{FiltrOption.BERUF.value}")],
            [InlineKeyboardButton(text="🔄 Застосувати фільтри", callback_data=f"apply_filters")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"mainMenu")]
        ])
    
    if is_new_mess:
        await message.answer(f"Ласкаво просимо до бота пошуку вакансій! Оберіть дію:", parse_mode=ParseMode.HTML, reply_markup=keyboard)
    else:
        await message.edit_text(f"Ласкаво просимо до бота пошуку вакансій! Оберіть дію:", parse_mode=ParseMode.HTML, reply_markup=keyboard)

async def generate_filtr_cat_btns(mn_dict:dict, params:list|str, tp:str, all_btn=True):
    inline_keyboard = []
    if (all_btn):
        txt = f"{'✅' if not params else ''} Вибрано всі!"
        inline_keyboard.append([InlineKeyboardButton(text=txt, callback_data=f"filtrVal_{tp}_All")])

    for index, (key, val) in enumerate(mn_dict.items()):
        if type(params) == str:
            txt = f"{'✅' if params and key.strip() == params.strip() else ''}{val}" 
        else:   
            txt = f"{'✅' if params and key in params else ''}{val}" 
        inline_keyboard.append([InlineKeyboardButton(text=txt, callback_data=f"filtrVal_{tp}_{index}")])

    inline_keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"scraperFiltrs")])

    return inline_keyboard

async def select_filtr_cat_btn(message: Message, filtr_type: str, filtr_index: str, is_new_mess: bool = True):
    # Функція для обробки фільтрів
    def toggle_filter_param(param_list: List[str], key: str):
        if not param_list:
            param_list = []  # Ініціалізуємо список, якщо він None
        if key in param_list:
            param_list.remove(key)  # Видаляємо, якщо вже є
        else:
            param_list.append(key)  # Додаємо, якщо немає
        return param_list

    # Якщо вибрано "All", очищаємо параметр
    if filtr_index == "All":
        if filtr_type == FiltrOption.BERUF.value:
            services.job_params.beruf = None
        elif filtr_type == FiltrOption.BRANCH.value:
            services.job_params.branch = None
        elif filtr_type == FiltrOption.AVAILABILITY.value:
            services.job_params.availability = None
        elif filtr_type == FiltrOption.PUBLISHED.value:
            services.job_params.time_slot = None
    else:
        fi = int(filtr_index)

        # Обробка фільтру 'beruf'
        if filtr_type == FiltrOption.BERUF.value:
            key = list(BERUF_DICT)[fi]
            services.job_params.beruf = toggle_filter_param(services.job_params.beruf, key)

        # Обробка фільтру 'branch'
        elif filtr_type == FiltrOption.BRANCH.value:
            key = list(BRANCH_DICT)[fi]
            services.job_params.branch = toggle_filter_param(services.job_params.branch, key)

        # Обробка фільтру 'arbeitszeit [Availability]'
        elif filtr_type == FiltrOption.AVAILABILITY.value:
            key = list(AVAIL_DICT)[fi]
            services.job_params.availability = toggle_filter_param(services.job_params.availability, key)
        
        # Обробка фільтру 'veroeffentlichtseit [TimeSlot]'
        elif filtr_type == FiltrOption.PUBLISHED.value:
            key = list(TIME_DICT)[fi]
            services.job_params.time_slot = f"{key}"

        # Інші фільтри можна обробляти тут подібно

    # Викликаємо обробник меню
    await filtr_cat_menu_handler(message, filtr_type, is_new_mess)

async def filtr_cat_menu_handler(message: Message, filtr_cat:FiltrOption, is_new_mess:bool=True):
    inline_keyboard = []
    txt = "Немає даних"

    message.answer_document

    if filtr_cat == FiltrOption.BERUF.value:
        txt = "Оберіть професію:"
        inline_keyboard = await generate_filtr_cat_btns(BERUF_DICT, services.job_params.beruf, FiltrOption.BERUF.value, True)
    if filtr_cat == FiltrOption.BRANCH.value:
        txt = "Оберіть галузь:"
        inline_keyboard = await generate_filtr_cat_btns(BRANCH_DICT, services.job_params.branch, FiltrOption.BRANCH.value, True)
    if filtr_cat == FiltrOption.AVAILABILITY.value:
        txt = "Тип зайнятості:"
        inline_keyboard = await generate_filtr_cat_btns(AVAIL_DICT, services.job_params.availability, FiltrOption.AVAILABILITY.value, True)
    if filtr_cat == FiltrOption.PUBLISHED.value:
        txt = "Оберіть період розміщення вакансій:"
        inline_keyboard = await generate_filtr_cat_btns(TIME_DICT, services.job_params.time_slot, FiltrOption.PUBLISHED.value, True)
    
    keyboard = InlineKeyboardMarkup(
    row_width=1,
    inline_keyboard=inline_keyboard)


    if is_new_mess:
        await message.answer(txt, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    else:
        await message.edit_text(txt, parse_mode=ParseMode.HTML, reply_markup=keyboard)

# Отримати баланс сервісу 2Captcha
async def get_two_captcha_service_balance(message: Message, is_new_mess:bool=True):
    scraper, _ = await services.initialize()
    balance_txt = await scraper.get_captcha_balance()

    keyboard = InlineKeyboardMarkup(
    row_width=2,
    inline_keyboard=[
            [InlineKeyboardButton(text="Закрити", callback_data=f"closeElement")]
        ])

    if True:
        await message.answer(balance_txt, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    else:
        await message.edit_text(balance_txt, parse_mode=ParseMode.HTML, reply_markup=keyboard)

def clean_txt(txt: str) -> str:
    """
    Прибирає переноси рядків та зайві пробіли .
    """
    if not isinstance(txt, str):
        return txt
    return ' '.join(txt.replace('\r', ' ').replace('\n', ' ').split())

# Відправка csv
async def create_and_send_csv(message: types.Message, max_old=None, session_id=None):
    """
    Створює CSV-файл із переданого списку та надсилає його в Telegram.
    """
    scraper, db_controller = await services.initialize()

    file_name = "data/example.csv"
    # Створення CSV-файлу
    with open(file_name, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        # Записуємо заголовки (опціонально)
        writer.writerow([
            "Назва вакансії", "Місцезнаходження", "Тип зайнятості", 
            "Дата розміщення", "Роботодавець", "Електронна пошта", 
            "Мобільний номер", "Ім’я та прізвище керівника", 
            "Поштова адреса", "Посилання на вакансію"
        ])
        # Записуємо дані
        ds = await db_controller.get_all_adverts(max_old=max_old, session_id=session_id)
        for dl in ds:
            writer.writerow([
                clean_txt(dl["title"]), clean_txt(dl["location"]), dl["type_offer"], 
                dl["posted_date"], dl["employer_company_name"], 
                dl["email"], dl["phone"], dl["employer_contact_person"], 
                dl["address"], dl["link"]
            ])
    
    # Відправка файлу через Telegram-бота
    try:
        # Передаємо файл через FSInputFile
        document = types.FSInputFile(file_name)
        await message.answer_document(document)
    except Exception as e:
        print("Помилка в відправці csv:", e)

# Обробка callback_handler
async def procc_callback_handler(callback: CallbackQuery, state: FSMContext):
    callback_data = callback.data 
    callback_list = callback_data.split("_")

    code = callback_list[0]
    
    if code == "searchVcn":
        await launch_handler(callback.message)
    elif code == "scraperFiltrs":
        await filtr_menu_handler(callback.message, False)
    elif code == "downloadResultMenu":
        await result_menu_handler(callback.message, False)
    elif code == "getCaptchaBalance":
        await get_two_captcha_service_balance(callback.message)
    elif code == "res":
        filtr_days = callback_list[1]
        
        try:
            filtr_days = int(filtr_days)
        except:
            filtr_days = 1
        
        await create_and_send_csv(callback.message, max_old=filtr_days)
    elif code == "mainMenu":
        await main_menu_handler(callback.message, False)  

    elif code == "filtr":
        filtr_type = callback_list[1]
        await filtr_cat_menu_handler(callback.message, filtr_type, False)
    elif code == "filtrVal":
        filtr_type = callback_list[1]
        filtr_index = callback_list[2]

        await select_filtr_cat_btn(callback.message, filtr_type, filtr_index, False)
    elif code == "apply_filters":
        await launch_handler(callback.message)

    elif code == "closeElement" :
        await callback.message.delete()


# Реєстратор
def register_handlers(dp: Dispatcher):
    # Реєстрація обробників команд
    dp.message.register(main_menu_handler, Command("start"))
    dp.message.register(create_and_send_csv, Command("res"))
    dp.message.register(launch_handler, Command("launch"))
    dp.message.register(stop_handler, Command("stop"))
    dp.message.register(get_id_handler, Command("id"))
    dp.message.register(get_two_captcha_service_balance, Command("tcp"))