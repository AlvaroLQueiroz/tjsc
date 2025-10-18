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

        self.loader = ttk.Progressbar(self, mode=self.mode, maximum=maximum, value=0)
        self.loader.pack(pady=20, padx=100, fill="x")

        self.updated_count = tk.IntVar(value=0)
        self.percentage = tk.StringVar(value="0%")
        self.loader["variable"] = self.updated_count
        self.updated_label = ttk.Label(self, textvariable=self.percentage)

        if mode == "determinate":
            self.updated_label.pack(pady=5)

        self.label = ttk.Label(self, text=text)
        self.label.pack(pady=5)

        self.loader.start()

    def update_progress(self):
        current = self.updated_count.get()
        self.updated_count.set(current + 1)
        if self.mode == "determinate":
            total = self.loader["maximum"]
            print(total, current)
            percent = int((current / total) * 100) if total > 0 else 0
            self.percentage.set(f"{percent}%")

    def set_text(self, text: str):
        self.label["text"] = text

    def set_mode(self, mode: LoadingMode):
        self.mode = mode
        self.loader["mode"] = mode
        if mode == "determinate":
            self.reset_progress()
            self.updated_label.pack(pady=5)
        else:
            self.updated_label.pack_forget()

    def set_maximum(self, maximum: int):
        self.loader["maximum"] = maximum

    def reset_progress(self):
        self.updated_count.set(0)
        if self.mode == "determinate":
            self.percentage.set("0%")
