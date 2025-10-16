import tkinter as tk
from async_tkinter_loop import async_handler
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page

from src.constants import ACTION_TIMEOUT, DOMAIN, STATE_PATH, NAVIGATION_TIMEOUT, ACTION_TIMEOUT
from src.crawler.locator import get_my_locators
from src.crawler.login import is_logged_in

from src.crawler.process import get_processes
from src.dto import LocatorsMap
from src.interface.loading import LoadingFrame
from src.interface.login import LoginFrame
from src.interface.select_parameters import SelectParametersFrame

is_user_logged_in: tk.BooleanVar = None
is_navigator_ready: tk.BooleanVar = None
locator_list: tk.StringVar = None

playwright: Playwright = None
browser: Browser = None
context: BrowserContext = None
page: Page = None

PIECES_DOCS_MAPS = {
    "Apelação": ["APE"],
    "Agravo de Instrumento": ["INIC"],
    "Contra-razões": ["CONTRAZAP"],
    "Parecer do Ministério Público": ["PROMOÇÃO"],
}
available_locators = {}

loading_frame: LoadingFrame = None
login_frame: LoginFrame = None


def start_application():
    global is_user_logged_in
    global is_navigator_ready
    global loading_frame
    global login_frame
    global locators_map

    # Initial states
    is_user_logged_in = tk.BooleanVar(value=False)
    is_navigator_ready = tk.BooleanVar(value=False)
    locators_map = LocatorsMap(value="")

    # Frames
    loading_frame = LoadingFrame(app, text="Validando sessão...")

    # Event listeners
    is_navigator_ready.trace_add("write", check_login_status)
    is_user_logged_in.trace_add("write", update_login)
    locators_map.trace_add("write", show_locators)

    # Starting point
    loading_frame.pack(fill="both", expand=True)
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
            f"--window-size={app.width},{app.height}",
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


def check_login_status(*args):
    async_handler(is_logged_in)(page, is_user_logged_in.set)


def update_login(*args):
    global login_frame

    if is_user_logged_in.get() is True:
        get_user_locators(app)
    else:
        loading_frame.pack_forget()
        login_frame = LoginFrame(app, page=page, context=context)
        login_frame.bind("<<LoginSuccess>>", get_user_locators)
        login_frame.pack(fill="both", expand=True)


def get_user_locators(*args):
    loading_frame.set_text("Aguarde...")
    async_handler(get_my_locators)(page, locators_map.set)


def show_locators(*args):
    global locator_frame

    loading_frame.pack_forget()
    locator_frame = SelectParametersFrame(
        app,
        locators=list(locators_map.keys()),
        pieces=list(PIECES_DOCS_MAPS.keys())
    )
    locator_frame.bind("<<ParametersSelected>>", crawler_files)
    locator_frame.pack(fill="both", expand=True)


def crawler_files(e):
    locator = locator_frame.selected_locator.get()
    piece = locator_frame.selected_piece.get()
    key_words = locator_frame.selected_key_words.get()
    locator_frame.pack_forget()
    loading_frame = LoadingFrame(app, text="Baixando arquivos...", mode="determinate", maximum=10)
    loading_frame.pack(fill="both", expand=True)
    async_handler(get_processes)(page, locator, print)
    locator_frame.pack_forget()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TJSC Robot")
        self.width = self.winfo_screenwidth()
        self.height = int(self.winfo_screenheight() / 2)
        self.geometry(f"{self.width}x{self.height}")

        # This is necessary to wait the async loop to start
        self.after(20, start_application)

app = App()
