import tkinter as tk
from tkinter import ttk
from typing import Literal

from src.interface.logo import LogoTitle


LoadingMode = Literal["determinate", "indeterminate"]


class LoadingFrame(ttk.Frame):
    def __init__(self, parent, text: str, mode: LoadingMode = "indeterminate", maximum: int = 100, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.mode = mode

        self.logo = LogoTitle(self)
        self.logo.pack(fill="y", pady=20)

        self.loader = ttk.Progressbar(self, mode=self.mode, maximum=maximum)
        self.loader.pack(pady=20, padx=100, fill="x")

        if mode == "determinate":
            self.updated_count = tk.IntVar(value=0)
            self.percentage = tk.StringVar(value="0%")
            self.updated_label = ttk.Label(self, textvariable=self.percentage)
            self.updated_label.pack(pady=5)

        self.label = ttk.Label(self, text=text)
        self.label.pack(pady=5)

        self.loader.start()

    def update_progress(self):
        current = self.updated_count.get()
        self.updated_count.set(current + 1)
        if self.mode == "determinate":
            total = self.loader["maximum"]
            percent = int((current / total) * 100) if total > 0 else 0
            self.percentage.set(f"{percent}%")

    def set_text(self, text: str):
        self.label["text"] = text
