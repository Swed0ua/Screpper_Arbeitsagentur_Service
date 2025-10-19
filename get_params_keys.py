import asyncio
import json
import os
import time
from datetime import datetime
from asyncio import Lock
import aiofiles
import phonenumbers
import dateparser
from modules.PlayWrightManager.await_manager import PWBrowserManager


URL = "https://www.arbeitsagentur.de/jobsuche/suche?angebotsart=1&id=12739-QO55QBPZQZSPHZSL-S"
filtr_item_id_name = '#branche-akkordeon'

async def write_to_file_async(file_name:str, txt:str):
    async with aiofiles.open(file_name, "w", encoding="utf-8") as file:
        await file.write(txt)

async def confirm_modal_cookie(page):
    modal_container = page.locator("#bahf-cookie-disclaimer-modal")
    if await modal_container.count() > 0:
        modal_comfirm_btn = modal_container.locator(".modal-footer").locator(".ba-btn-primary")
        await modal_comfirm_btn.click(force=True)
        await page.wait_for_timeout(2000)

async def get_params_list(page):
    filtr_item_area = page.locator(filtr_item_id_name)
    await filtr_item_area.scroll_into_view_if_needed()
    filtr_item_param_list = filtr_item_area.locator('.filter-fieldset-liste')
    
    all_params = filtr_item_param_list.locator(".filter-fieldset-item")
    all_params_list_count = await all_params.count()

    print('Count param items:', all_params_list_count)

    return all_params, all_params_list_count

async def main(url: str):
    browser_manager = PWBrowserManager()
    page = await browser_manager.get_browser(is_headless=False)
    try:
        await page.goto(url)
        await page.wait_for_timeout(5000)  # Чекаємо для демонстрації

        await confirm_modal_cookie(page)

        await page.click("button#filter-toggle", force=True)
        await page.wait_for_timeout(1000) 

        all_params, all_params_list_count = await get_params_list(page)

        if all_params_list_count <= 0 :
            await page.click(filtr_item_id_name,force=True)
            await page.wait_for_timeout(2000)
            all_params, all_params_list_count = await get_params_list(page)
        
        txt_result = ""
        
        for i in range(all_params_list_count):
            param_item = all_params.nth(i)
            param_title = await param_item.locator("label").inner_text()
            txt_result += f"{param_title.strip()}\n"
            print('txt - ', await param_item.inner_text())

        await write_to_file_async(f"txt{filtr_item_id_name}.txt" ,txt_result)

        await page.wait_for_timeout(15000)
    except Exception as e:
        print('error', e)
    finally:
        # Закриття браузера
        await browser_manager.close_browser()

name = "branche-akkordeon"

with open(f'txt#{name}.txt', "r", encoding='utf-8') as f:
    a = f.read()
    b = a.splitlines()

print(b)

new_txt = ""
new_dict = {}
for i in b:
    new_i = i.strip().replace(" ",'%20').replace("/", "%2F").strip()
    new_txt += f"{i}|||{new_i}\n"
    new_dict[new_i] = i


with open(f'{name}.json', "w", encoding="utf-8") as file:
    json.dump(new_dict, file, ensure_ascii=False, indent=4)

# if __name__ == "__main__":
#     asyncio.run(main(URL))