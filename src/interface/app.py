import tkinter as tk
from async_tkinter_loop import async_handler
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page

from src.constants import ACTION_TIMEOUT, DOMAIN, STATE_PATH, NAVIGATION_TIMEOUT, ACTION_TIMEOUT

from src.crawler.process import get_processes
from src.dto import DictVar
from src.interface.loading import LoadingFrame
from src.interface.login import LoginPage
from src.interface.select_parameters import SelectParametersFrame
from src.interface.root import rootWindow

is_user_logged_in: tk.BooleanVar = None
is_navigator_ready: tk.BooleanVar = None
locator_list: tk.StringVar = None

playwright: Playwright = None
browser: Browser = None
context: BrowserContext = None
page: Page = None

available_locators = {}

loading_frame: LoadingFrame = None
login_frame: LoginPage = None


def start_application():
    global is_user_logged_in
    global is_navigator_ready
    global loading_frame
    global locators_map

    # Initial states
    is_user_logged_in = tk.BooleanVar(value=False)
    is_navigator_ready = tk.BooleanVar(value=False)
    locators_map = DictVar(value="")

    # Frames
    loading_frame = LoadingFrame(rootWindow, text="Validando sessão...")

    # Event listeners
    is_navigator_ready.trace_add("write", show_login_page)
    # is_user_logged_in.trace_add("write", update_login)
    locators_map.trace_add("write", show_locators)

    # Starting point
    async_handler(start_navigator)()


async def start_navigator():
    global playwright
    global browser
    global context
    global page

    playwright = await async_playwright().start()
    browser = await playwright.webkit.launch(
        args=[
            f"--window-position=0,0",
            f"--window-size={rootWindow.width},{rootWindow.height}",
        ],
        headless=False,
        slow_mo=ACTION_TIMEOUT // 5
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


async def stop_navigator():
    await page.close()
    await context.close()
    await browser.close()
    await playwright.stop()


def show_login_page(*args):
    global login_frame

    login_frame = LoginPage(rootWindow, page, context)
    login_frame.bind("<<LoginSuccess>>", show_locators)
    login_frame.pack(fill="both", expand=True)


def show_locators(*args):
    global locator_frame

    loading_frame.pack_forget()
    locator_frame = SelectParametersFrame(rootWindow, page, context)
    locator_frame.bind("<<ParametersSelected>>", crawler_files)
    locator_frame.pack(fill="both", expand=True)


def crawler_files(e):
    locator = locator_frame.selected_locator.get()
    piece = locator_frame.selected_piece.get()
    key_words = locator_frame.selected_key_words.get()
    locator_frame.pack_forget()
    loading_frame = LoadingFrame(rootWindow, text="Baixando arquivos...", mode="determinate", maximum=10)
    loading_frame.pack(fill="both", expand=True)
    async_handler(get_processes)(page, locator, print)
    locator_frame.pack_forget()
