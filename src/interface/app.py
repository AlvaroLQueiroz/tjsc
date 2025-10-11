from functools import partial
import tkinter as tk
from tracemalloc import stop
from async_tkinter_loop import async_handler
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page

from src.constants import DOMAIN, DATA_PATH
from src.crawler.login import is_logged_in

from src.interface.loading import LoadingFrame
from src.interface.login import LoginFrame


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TJSC Robot")
        self.width = self.winfo_screenwidth()
        self.height = int(self.winfo_screenheight() / 2)
        self.geometry(f"{self.width}x{self.height}")

        self.is_user_logged_in = tk.BooleanVar(value=False)
        self.is_navigator_ready = tk.BooleanVar(value=False)

        self.playwright: Playwright = None
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.page: Page = None

        self.loading_frame = LoadingFrame(self)
        self.login_frame = LoginFrame(self)

        self.loading_frame.pack(fill="both", expand=True)

        # This is necessary to wait the async loop to start
        self.after(2000, self.start_application)

    def start_application(self):
        self.is_navigator_ready.trace_add("write", partial(self.check_login_status, self))
        self.is_user_logged_in.trace_add("write", partial(self.update_login, self))
        self.login_frame.bind("<<LoginSuccess>>", partial(self.select_parameters, self))

        async_handler(self.start_navigator)(self)

    @staticmethod
    async def start_navigator(app: "App"):
        app.playwright = await async_playwright().start()
        app.browser = await app.playwright.webkit.launch(
            args=[
                f"--window-position=0,0",
                f"--window-size={app.width},{app.height}",
            ],
            headless=False,
            slow_mo=800
        )
        app.context = await app.browser.new_context(
            base_url=DOMAIN, storage_state=DATA_PATH / "state.json"
        )
        app.page = await app.context.new_page()
        app.is_navigator_ready.set(True)

    @staticmethod
    async def stop_navigator(root: "App"):
        await root.page.close()
        await root.context.close()
        await root.browser.close()
        await root.playwright.stop()

    def check_login_status(self, *args):
        async_handler(is_logged_in)(self.page, self.is_user_logged_in.set)

    def update_login(self, *args):
        self.loading_frame.destroy()
        if self.is_user_logged_in.get() is True:
            pass
        else:
            self.login_frame.pack(fill="both", expand=True)

    def select_parameters(self, *args):
        pass
