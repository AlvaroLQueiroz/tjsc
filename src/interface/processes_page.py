import os
from urllib.parse import parse_qs, urlparse
import webbrowser
import tkinter as tk
from tkinter import ttk

from async_tkinter_loop import async_handler
from playwright.async_api import BrowserContext, Page

from src.constants import DOMAIN, DOWNLOADED_PATH, EPROC, EPROC_CONTROLADOR


class ProcessesPage(ttk.LabelFrame):
    def __init__(self, parent: tk.Tk, page: Page, context: BrowserContext):
        super().__init__(parent)
        self.page = page
        self.context = context

        self.text = "Processos Baixados"
        self.tree = ttk.Treeview(self, columns=("col1"), show="tree", cursor="hand1")

        for process_number in DOWNLOADED_PATH.iterdir():
            if process_number.is_dir():
                self.tree.insert(
                    parent="",
                    index="end",
                    iid=process_number.name,
                    text=process_number.name,
                    open=True,
                    tags=("process_button",),
                )

        for pdf_file in DOWNLOADED_PATH.glob("**/*.pdf"):
            process_number = pdf_file.parent.name
            file_name = pdf_file.name
            self.tree.insert(
                parent=process_number,
                index="end",
                text=file_name,
                tags=("file_button",),
            )

        self.tree.tag_bind("file_button", "<Double-Button-1>", self.handle_file_click)
        self.tree.tag_bind(
            "process_button",
            "<Double-Button-1>",
            async_handler(self.handle_process_click),
        )
        self.tree.pack(fill="both", expand=True)

        self.restart_button = ttk.Button(
            self, text="Nova Consulta", command=self.restart_crawling
        )
        self.restart_button.pack(pady=10)

    def handle_file_click(self, event):
        item = self.tree.identify("item", event.x, event.y)
        file_name = self.tree.item(item, "text")
        process_number = self.tree.item(self.tree.parent(item), "text")
        if file_name:
            file_path = DOWNLOADED_PATH / process_number / file_name
            if os.name == "nt":
                os.startfile(file_path)  # For Windows
            elif os.name == "posix":
                os.system(f'open "{file_path}"')  # For macOS
            else:
                os.system(f'xdg-open "{file_path}"')  # For Linux

    async def handle_process_click(self, event):
        item = self.tree.identify("item", event.x, event.y)
        process_number = self.tree.item(item, "text")
        self.clipboard_clear()
        self.clipboard_append(process_number)

    def restart_crawling(self):
        self.event_generate("<<RestartCrawling>>")
        self.destroy()
