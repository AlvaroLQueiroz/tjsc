import tkinter as tk
from async_tkinter_loop import async_handler
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page

from src.constants import DOMAIN, DATA_PATH
from src.crawler import locator
from src.crawler.login import is_logged_in

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


loading_frame: LoadingFrame = None
login_frame: LoginFrame = None


def start_application():
    global is_user_logged_in
    global is_navigator_ready
    global loading_frame
    global login_frame
    global locator_list

    is_user_logged_in = tk.BooleanVar(value=False)
    is_navigator_ready = tk.BooleanVar(value=False)
    locator_list = tk.StringVar(value="")

    loading_frame = LoadingFrame(app, text="Validando sessão...")
    loading_frame.pack(fill="both", expand=True)
    is_navigator_ready.trace_add("write", check_login_status)
    is_user_logged_in.trace_add("write", update_login)

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
        headless=True,
        slow_mo=0
    )
    context = await browser.new_context(
        base_url=DOMAIN, storage_state=DATA_PATH / "state.json"
    )
    page = await context.new_page()
    is_navigator_ready.set(True)


async def stop_navigator():
    await page.close()
    await context.close()
    await browser.close()
    await playwright.stop()


def check_login_status(*args):
    async_handler(is_logged_in)(page, is_user_logged_in.set)


def update_login(*args):
    loading_frame.pack_forget()
    if is_user_logged_in.get() is True:
        select_parameters(app)
    else:
        login_frame = LoginFrame(app, page=page, context=context)
        login_frame.bind("<<LoginSuccess>>", select_parameters)
        login_frame.pack(fill="both", expand=True)


def select_parameters(*args):
    loading_frame.set_text("Aguarde...")
    loading_frame.pack(pady=20)
    async_handler(locator.get_my_locators)(page, locator_list.set)
    def show_locators(*args):
        loading_frame.pack_forget()
        locator_frame = SelectParametersFrame(app, locators=locator_list.get())
        locator_frame.pack(fill="both", expand=True)
    locator_list.trace_add("write", show_locators)


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
