import tkinter as tk

class RootWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TJSC Robot")
        self.width = self.winfo_screenwidth()
        self.height = int(self.winfo_screenheight() / 2)
        self.geometry(f"{self.width}x{self.height}")


rootWindow = RootWindow()
