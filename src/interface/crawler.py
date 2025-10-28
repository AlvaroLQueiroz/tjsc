import logging
import shutil

import tkinter as tk
from tkinter import ttk

from async_tkinter_loop import async_handler
from playwright.async_api import BrowserContext, Page

from src.constants import DOWNLOADED_PATH, PIECES_DOCS_MAPS
from src.dto import DictVar
from src.interface.loading import LoadingFrame
from pathlib import Path
import re


from src.crawler.process import download_process_files, get_processes
from src.ocr import extract_text_from_pdf

logger = logging.getLogger(__name__)


class CrawlerPage(ttk.Frame):
    PIECES_KEYS = list(PIECES_DOCS_MAPS.keys())

    def __init__(self, parent: tk.Tk, page: Page, context: BrowserContext, locator: str, piece: str, key_words: str):
        super().__init__(parent)
        self.page = page
        self.context = context
        self.locator = locator
        self.piece = piece
        self.key_words = key_words

        self.processes = DictVar()
        self.files = DictVar()

        self.loading_frame: LoadingFrame = LoadingFrame(self, text="", mode="determinate")
        self.loading_frame.pack(fill="both", expand=True)

    async def crawler_processes(self):
        shutil.rmtree(DOWNLOADED_PATH, ignore_errors=True)  # Clean previous downloads in
        DOWNLOADED_PATH.mkdir(parents=True, exist_ok=True)
        self.loading_frame.set_text("Coletando processos...")
        self.loading_frame.reset_progress()
        self.loading_frame.pack(fill="both", expand=True)
        self.processes.trace_add("write", async_handler(self.download_files))
        await get_processes(self.page, self.locator, self.loading_frame, self.processes.set)

    async def download_files(self, *args):
        self.loading_frame.set_text("Baixando arquivos dos processos...")
        self.loading_frame.reset_progress()
        self.files.trace_add("write", async_handler(self.process_downloaded_files))
        await download_process_files(
            self.page,
            self.processes.get(),
            PIECES_DOCS_MAPS[self.piece],
            self.files.set,
            self.loading_frame
        )

    async def process_downloaded_files(self, *args) -> None:
        self.loading_frame.set_text("Processando arquivos dos processos...")
        self.loading_frame.reset_progress()
        pattern = re.compile(self.key_words, re.IGNORECASE|re.DOTALL|re.MULTILINE)

        for process_number, process in self.processes.items():
            self.loading_frame.update_progress()
            for file_path in process.get("files", []):
                file_content = await extract_text_from_pdf(Path(file_path))
                if not pattern.match(file_content):
                    logger.info(f"Process {process_number}: Key words not found in file {file_path}")
                    Path(file_path).unlink(missing_ok=True)

        self.event_generate("<<CrawlingFinished>>")
        self.destroy()
