import tkinter as tk
from tkinter import ttk

from async_tkinter_loop import async_handler
from playwright.async_api import BrowserContext, Page

from src.crawler.login import is_logged_in, make_login
from src.dto import DictVar
from src.interface.loading import LoadingFrame
from src.interface.logo import LogoTitle


class LoginPage(ttk.Frame):
    def __init__(self, parent, page, context):
        super().__init__(parent)
        self.page: Page = page
        self.context: BrowserContext = context

        self.username = tk.StringVar()
        self.password = tk.StringVar()
        self.otp_code = tk.StringVar()
        self.status = DictVar()

        self.status.trace_add("write", self.handle_status_change)

        self.loading_frame = LoadingFrame(self, text="Validando sessão...")
        self.loading_frame.pack(fill="both", expand=True)
        self.check_login_status()

    def setup_ui(self):
        self.loading_frame.pack_forget()

        self.logo = LogoTitle(self)
        self.logo.pack(fill="y", pady=20)

        self.user_label = ttk.Label(self, text="Usuário:")
        self.user_label.pack(pady=5)
        self.user_entry = ttk.Entry(self, textvariable=self.username)
        self.user_entry.pack(pady=5)

        self.password_label = ttk.Label(self, text="Senha:")
        self.password_label.pack(pady=5)
        self.password_entry = ttk.Entry(self, textvariable=self.password, show="*")
        self.password_entry.pack(pady=5)

        self.otp_label = ttk.Label(self, text="Código de autenticação:")
        self.otp_label.pack(pady=5)
        self.otp_entry = ttk.Entry(self, textvariable=self.otp_code)
        self.otp_entry.bind("<Return>", self.dispatch_login)
        self.otp_entry.pack(pady=5)

        self.button = ttk.Button(self, text="Confirmar", command=self.dispatch_login)
        self.button.bind("<Return>", self.dispatch_login)
        self.button.pack(pady=5)

        self.error_label = ttk.Label(self, text="Error ao fazer login.", foreground="red")

    def check_login_status(self, *args):
        async_handler(is_logged_in)(self.page, self.status.set)

    def dispatch_login(self, event: tk.Event | None = None):
        self.error_label.pack_forget()
        self.loading_frame.pack(fill="both", expand=True)
        username = self.username.get()
        password = self.password.get()
        otp_code = self.otp_code.get()
        async_handler(make_login)(
            username,
            password,
            otp_code,
            self.page,
            self.context,
            self.status.set
        )

    def handle_status_change(self, *args):
        status = self.status.get()
        if status.get("logged_in") is True:
            self.loading_frame.destroy()
            self.event_generate("<<LoginSuccess>>")
            self.destroy()
        elif status.get("message"):
            self.loading_frame.pack_forget()
            self.error_label.config(text=status.get("message"))
            if not self.error_label.winfo_ismapped():
                self.error_label.pack(pady=5)
        else:
            self.setup_ui()
