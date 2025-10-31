import logging

import subprocess
import tkinter as tk
from async_tkinter_loop import async_handler
from playwright.async_api import (
    async_playwright,
    Playwright,
    Browser,
    BrowserContext,
    Page,
)

from src.constants import (
    ACTION_TIMEOUT,
    DOMAIN,
    STATE_PATH,
    NAVIGATION_TIMEOUT,
    ACTION_TIMEOUT,
)
from src.dto import DictVar
from src.interface.crawler import CrawlerPage
from src.interface.login import LoginPage
from src.interface.processes_page import ProcessesPage
from src.interface.select_parameters import ParametersPage
from src.interface.root import rootWindow

is_navigator_ready: tk.BooleanVar = None
processes = DictVar()
files = DictVar()

playwright: Playwright = None
browser: Browser = None
context: BrowserContext = None
page: Page = None

logger = logging.getLogger(__name__)

def start_application():
    global is_navigator_ready
    global loading_frame

    logger.debug("########## Starting application ##########")
    # Initial states
    is_navigator_ready = tk.BooleanVar(value=False)

    # Event listeners
    is_navigator_ready.trace_add("write", show_login_page)
    # rootWindow.protocol("WM_DELETE_WINDOW", async_handler(stop_navigator))

    # Starting point
    async_handler(start_navigator)()


async def start_navigator():
    global playwright
    global browser
    global context
    global page

    logger.debug("Starting Playwright navigator...")
    playwright = await async_playwright().start()

    try:
        browser = await playwright.webkit.launch(
            headless=False,
        )
    except Exception as e:
        logger.error(f"Failed to start Playwright: {e}")
        subprocess.run(["playwright", "install", "chromium"], check=True)
        browser = await playwright.webkit.launch(
            headless=False,
        )
    context = await browser.new_context(
        **playwright.devices["Desktop Chrome"],
        base_url=DOMAIN,
        storage_state=STATE_PATH,
    )
    page = await context.new_page()
    page.set_default_navigation_timeout(NAVIGATION_TIMEOUT)
    page.set_default_timeout(ACTION_TIMEOUT)
    is_navigator_ready.set(True)
    logger.debug("Playwright navigator started successfully.")


async def stop_navigator():
    if not page:
        return
    await page.close()
    await context.close()
    await browser.close()
    await playwright.stop()
    rootWindow.destroy()


def show_login_page(*args):
    login_frame = LoginPage(rootWindow, page, context)
    login_frame.bind("<<LoginSuccess>>", show_parameters_page)
    login_frame.pack(fill="both", expand=True)


def show_parameters_page(*args):
    parameters_page = ParametersPage(rootWindow, page, context)
    parameters_page.bind("<<ParametersSelected>>", show_crawler_page)
    parameters_page.pack(fill="both", expand=True)


def show_crawler_page(e):
    locator = e.widget.selected_locator.get()
    piece = e.widget.selected_piece.get()
    key_words = e.widget.selected_key_words.get()
    crawler_page = CrawlerPage(rootWindow, page, context, locator, piece, key_words)
    crawler_page.bind("<<CrawlingFinished>>", show_processes_page)
    crawler_page.pack(fill="both", expand=True)
    async_handler(crawler_page.crawler_processes)()


def show_processes_page(*args):
    processes_page = ProcessesPage(rootWindow, page, context)
    processes_page.bind("<<RestartCrawling>>", show_parameters_page)
    processes_page.pack(fill="both", expand=True)
