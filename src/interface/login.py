import tkinter as tk
from tkinter import ttk

from async_tkinter_loop import async_handler
from playwright.async_api import BrowserContext, Page

from src.crawler.login import make_login
from src.interface.logo import LogoTitle
from src.types import Status


class LoginFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.page: Page = parent.page
        self.context: BrowserContext = parent.context

        self.username = tk.StringVar()
        self.password = tk.StringVar()
        self.otp_code = tk.StringVar()
        self.login_status = tk.BooleanVar()

        self.login_status.trace_add("write", self.dispatch_login_status)

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
        self.otp_entry.bind("<Return>", self.confirm_login)
        self.otp_entry.pack(pady=5)

        self.button = ttk.Button(self, text="Confirmar", command=self.confirm_login)
        self.button.bind("<Return>", self.confirm_login)
        self.button.pack(pady=5)

        self.error_label = ttk.Label(self, text="Error ao fazer login.", foreground="red")

    def confirm_login(self, event: tk.Event | None = None):
        self.error_label.pack_forget()
        username = self.username.get()
        password = self.password.get()
        otp_code = self.otp_code.get()
        async_handler(make_login)(
            username,
            password,
            otp_code,
            self.page,
            self.context,
            self.login_status.set
        )

    def dispatch_login_status(self, *args):
        if self.login_status.get() is True:
            self.event_generate("<<LoginSuccess>>")
        else:
            self.error_label.pack(pady=5)
