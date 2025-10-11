import tkinter as tk
from async_tkinter_loop import async_handler
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page

from src.constants import DOMAIN, DATA_PATH
from src.crawler.locator import get_my_locators
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
    global locator_list

    # Initial states
    is_user_logged_in = tk.BooleanVar(value=False)
    is_navigator_ready = tk.BooleanVar(value=False)
    locator_list = tk.StringVar(value="")

    # Frames
    loading_frame = LoadingFrame(app, text="Validando sessão...")
    login_frame = LoginFrame(app, page=page, context=context)

    # Event listeners
    is_navigator_ready.trace_add("write", check_login_status)
    is_user_logged_in.trace_add("write", update_login)
    locator_list.trace_add("write", show_locators)
    login_frame.bind("<<LoginSuccess>>", get_user_locators)

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
    # async_handler(is_logged_in)(page, is_user_logged_in.set)
    is_user_logged_in.set(True)  # For testing purposes only

def update_login(*args):
    loading_frame.pack_forget()
    if is_user_logged_in.get() is True:
        get_user_locators(app)
    else:
        login_frame.pack(fill="both", expand=True)


def get_user_locators(*args):
    loading_frame.set_text("Aguarde...")
    loading_frame.pack(pady=20)
    # async_handler(get_my_locators)(page, locator_list.set)
    locator_list.set("|||".join(["Locator 1||http://example.com/1", "Locator 2||http://example.com/2"]))  # For testing purposes only


def show_locators(*args):
    global locator_frame

    loading_frame.pack_forget()
    for locator in locator_list.get().split("|||"):
        text, link = locator.split("||")
        available_locators[text] = link
    locator_frame = SelectParametersFrame(
        app,
        locators=list(available_locators.keys()),
        pieces=list(PIECES_DOCS_MAPS.keys())
    )
    locator_frame.bind("<<ParametersSelected>>", show)
    locator_frame.pack(fill="both", expand=True)

def show(e):
    print("Selected parameters:")
    print("Locator:", locator_frame.selected_locator.get())
    print("Piece:", locator_frame.selected_piece.get())
    print("Key words:", locator_frame.selected_key_words.get())
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
