import tkinter as tk


class RootWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TJSC Robot")
        self.width = 1024
        self.height = 768
        self.geometry(f"{self.width}x{self.height}")


rootWindow = RootWindow()
