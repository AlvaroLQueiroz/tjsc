import tkinter as tk
from tkinter import ttk
from typing import Literal

from src.interface.logo import LogoTitle


LoadingMode = Literal["determinate", "indeterminate"]


class LoadingFrame(ttk.Frame):
    def __init__(
        self,
        parent,
        text: str,
        mode: LoadingMode = "indeterminate",
        maximum: int = 100,
        *args,
        **kwargs,
    ):
        super().__init__(parent, *args, **kwargs)
        self.mode = mode

        self.logo = LogoTitle(self)
        self.logo.pack(fill="y", pady=20)

        self.counter = tk.IntVar(value=0)
        self.percentage = tk.StringVar(value="0%")

        self.loader = ttk.Progressbar(
            self, mode=self.mode, maximum=maximum, variable=self.counter
        )
        self.loader.pack(pady=20, padx=100, fill="x")

        self.label = ttk.Label(self, text=text)
        self.label.pack(pady=5)

        self.counter_label = ttk.Label(self, textvariable=self.percentage)
        if mode == "determinate":
            self.counter_label.pack(pady=5)
        else:
            self.loader.start()

    def update_progress(self):
        if self.mode == "indeterminate":
            return
        current = self.counter.get() or 0
        self.counter.set(current + 1)
        if self.mode == "determinate":
            total = self.loader["maximum"]
            percent = int((current / total) * 100) if total > 0 else 0
            self.percentage.set(f"{percent}%")

    def set_text(self, text: str):
        self.label["text"] = text

    def set_mode(self, mode: LoadingMode):
        self.mode = mode
        self.loader["mode"] = mode
        if mode == "determinate":
            self.reset_progress()
            self.counter_label.pack(pady=5)
            self.loader.stop()
        else:
            self.counter_label.pack_forget()
            self.loader.start()

    def set_maximum(self, maximum: int):
        self.loader["maximum"] = maximum

    def get_maximum(self) -> int:
        return self.loader["maximum"]

    def reset_progress(self):
        self.counter.set(0)
        if self.mode == "determinate":
            self.percentage.set("0%")
