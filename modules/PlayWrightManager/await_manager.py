import os
import random
import logging
from typing import Optional
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from playwright.async_api import async_playwright, Page, Browser, BrowserContext, Playwright


class PWBrowserManager:
    def __init__(self, proxy_file_path: Optional[str] = None, use_proxy: bool = True):
        self.use_proxy = use_proxy
        self.proxy_list = self._load_proxies(proxy_file_path)
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def _load_proxies(self, file_path: Optional[str]) -> list[str]:
        """Load proxy list from a file if provided."""
        if file_path and os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read().splitlines()
        logging.info("PWBrowserManager [_load_proxies]: Proxy file not found or not specified.")
        return []

    def _get_random_proxy(self) -> Optional[str]:
        """Retrieve a random proxy from the loaded proxy list."""
        return random.choice(self.proxy_list) if self.proxy_list else None

    def _get_random_user_agent(self) -> str:
        """Generate a random desktop user agent."""
        ua = UserAgent()

        def is_desktop_ua(user_agent: str) -> bool:
            return not any(keyword in user_agent for keyword in ["Mobile", "Android", "iPhone", "iPad"])

        while True:
            user_agent = random.choice([ua.chrome, ua.firefox, ua.safari])
            if is_desktop_ua(user_agent):
                return user_agent

    def _parse_proxy(self, proxy: str) -> dict:
        """Convert a proxy string into Playwright's proxy configuration."""
        proxy = proxy.lstrip("http://").replace('@', ':')
        try:
            username, password, host, port = proxy.split(':')
            return {
                "server": f"http://{host}:{port}",
                "username": username,
                "password": password,
            }
        except ValueError as e:
            logging.error(f"PWBrowserManager [_parse_proxy]: Invalid proxy format: {proxy}. Error: {e}")
            raise ValueError("Invalid proxy format. Expected format: username:password@host:port")

    async def initialize_browser(self, is_headless: bool = True, proxy_server: Optional[str] = None) -> Page:
        """Launch the browser and initialize a page."""
        self.playwright = await async_playwright().start()

        proxy_server = proxy_server or (self._get_random_proxy() if self.use_proxy else None)
        browser_options = {"headless": is_headless}

        if proxy_server:
            try:
                browser_options["proxy"] = self._parse_proxy(proxy_server)
            except ValueError:
                logging.warning("PWBrowserManager [initialize_browser]: Proxy configuration skipped due to error.")

        self.browser = await self.playwright.chromium.launch(**browser_options)
        self.context = await self.browser.new_context(
            user_agent=self._get_random_user_agent(),
            viewport=None
        )
        self.page = await self.create_new_page()
        return self.page
    
    async def create_new_page(self):
        page = await self.context.new_page()
        return page 

    async def restart_browser(self, is_headless: bool = True, proxy_server: Optional[str] = None) -> Page:
        """Restart the browser with new configurations."""
        await self.close_browser()
        return await self.initialize_browser(is_headless, proxy_server)

    async def block_unwanted_requests(self, resource_types: Optional[list[str]] = None):
        """Block unwanted network requests like images, stylesheets, etc."""
        resource_types = resource_types or ["image", "stylesheet", "font"]

        async def route_handler(route):
            if route.request.resource_type in resource_types:
                await route.abort()
            else:
                await route.continue_()

        if self.page:
            await self.page.route("**/*", route_handler)

    def parse_html_to_soup(self, element=None) -> BeautifulSoup:
        """Convert page content or specific element to BeautifulSoup object."""
        content = element.inner_html() if element else self.page.content()
        return BeautifulSoup(content, "html.parser")

    async def close_browser(self):
        """Close all Playwright instances."""
        if self.page:
            await self.page.close()
            self.page = None
        if self.context:
            await self.context.close()
            self.context = None
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
