import tkinter as tk
from tkinter import ttk

from src.constants import STATIC_PATH


class LogoTitle(ttk.Label):
    def __init__(self, parent):
        self.logo = tk.PhotoImage(file=STATIC_PATH / "logo_eproc.png")
        super().__init__(parent, image=self.logo)
