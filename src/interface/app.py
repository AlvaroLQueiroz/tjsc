from functools import partial
import tkinter as tk
from async_tkinter_loop import async_handler
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page

from src.constants import ACTION_TIMEOUT, DOMAIN, PIECES_DOCS_MAPS, STATE_PATH, NAVIGATION_TIMEOUT, ACTION_TIMEOUT

from src.crawler.process import download_process_files, get_processes
from src.dto import DictVar
from src.interface.loading import LoadingFrame
from src.interface.login import LoginPage
from src.interface.select_parameters import SelectParametersPage
from src.interface.root import rootWindow

is_navigator_ready: tk.BooleanVar = None
processes = DictVar()

playwright: Playwright = None
browser: Browser = None
context: BrowserContext = None
page: Page = None

loading_frame: LoadingFrame = None


def start_application():
    global is_navigator_ready
    global loading_frame

    # Initial states
    is_navigator_ready = tk.BooleanVar(value=False)

    # Frames
    loading_frame = LoadingFrame(rootWindow, text="Validando sessão...")

    # Event listeners
    is_navigator_ready.trace_add("write", show_login_page)

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
        # slow_mo=ACTION_TIMEOUT // 5
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
    login_frame = LoginPage(rootWindow, page, context)
    login_frame.bind("<<LoginSuccess>>", show_parameters_page)
    login_frame.pack(fill="both", expand=True)


def show_parameters_page(*args):
    global locator_frame

    loading_frame.destroy()
    locator_frame = SelectParametersPage(rootWindow, page, context)
    locator_frame.bind("<<ParametersSelected>>", crawler_processes)
    locator_frame.pack(fill="both", expand=True)


def crawler_processes(e):
    global processes
    global loading_frame

    locator = e.widget.selected_locator.get()
    piece = e.widget.selected_piece.get()
    key_words = e.widget.selected_key_words.get()
    loading_frame = LoadingFrame(rootWindow, text="Iniciando coleta de processos...", mode="determinate")
    loading_frame.pack(fill="both", expand=True)
    async_handler(get_processes)(page, locator, loading_frame, processes.set)

    processes.trace_add("write",  partial(download_files, piece, key_words))

def download_files(piece: str, key_words: str, *args):
    global loading_frame

    loading_frame.set_mode("determinate")
    loading_frame.set_text("Processando arquivos...")
    loading_frame.set_maximum(len(processes.get()))
    async_handler(download_process_files)(context, page, processes.get(), PIECES_DOCS_MAPS[piece], key_words, loading_frame)
