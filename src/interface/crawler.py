import logging
import shutil
from pathlib import Path

import tkinter as tk
from async_tkinter_loop import async_handler
from playwright.async_api import BrowserContext, Page
from tkinter import ttk

from src.constants import DOWNLOADED_PATH, PIECES_DOCS_MAPS
from src.crawler.process import download_process_files, get_processes
from src.dto import DictVar
from src.interface.loading import LoadingFrame
from src.ocr import extract_text_from_pdf
from src.text_searching import find_pattern_in_text

logger = logging.getLogger(__name__)


class CrawlerPage(ttk.Frame):
    PIECES_KEYS = list(PIECES_DOCS_MAPS.keys())

    def __init__(
        self,
        parent: tk.Tk,
        page: Page,
        context: BrowserContext,
        locator: str,
        piece: str,
        key_words: str,
    ):
        super().__init__(parent)
        logger.debug("Initializing Crawler with locator: %s, piece: %s, key_words: %s.", locator, piece, key_words)
        self.page = page
        self.context = context
        self.locator = locator
        self.piece = piece
        self.key_words = key_words

        self.processes = DictVar()
        self.files = DictVar()
        self.process_downloaded_files_trace_id = None
        self.download_files_trace_id = None

        self.loading_frame: LoadingFrame = LoadingFrame(
            self, text="", mode="determinate"
        )
        self.loading_frame.pack(fill="both", expand=True)

    async def crawler_processes(self):
        logger.debug("Removing previous downloaded files.")
        shutil.rmtree(
            DOWNLOADED_PATH, ignore_errors=True
        )  # Clean previous downloads in
        DOWNLOADED_PATH.mkdir(parents=True, exist_ok=True)
        self.loading_frame.set_text("Coletando processos...")
        self.loading_frame.reset_progress()
        self.loading_frame.pack(fill="both", expand=True)
        if self.process_downloaded_files_trace_id:
            self.processes.trace_remove(
                "write", self.process_downloaded_files_trace_id
            )
        self.download_files_trace_id = self.processes.trace_add("write", async_handler(self.download_files))
        await get_processes(
            self.page, self.locator, self.loading_frame, self.processes.set
        )

    async def download_files(self, *args):
        self.loading_frame.set_text("Baixando arquivos dos processos...")
        self.loading_frame.reset_progress()
        self.processes.trace_remove("write", self.download_files_trace_id)
        self.process_downloaded_files_trace_id = self.processes.trace_add("write", async_handler(self.process_downloaded_files))
        await download_process_files(
            self.page,
            self.processes.get(),
            PIECES_DOCS_MAPS[self.piece],
            self.processes.set,
            self.loading_frame,
        )

    async def process_downloaded_files(self, *args) -> None:
        logger.debug("Processing downloaded files for keyword filtering.")
        self.loading_frame.set_text("Processando arquivos dos processos...")
        self.loading_frame.reset_progress()

        logger.info(self.processes.items())
        for process_number, process in self.processes.items():
            self.loading_frame.update_progress()
            file_counter = 0
            logger.debug("Processing files for process %s", process_number)
            for file_path in process.get("files", []):
                file_content = await extract_text_from_pdf(Path(file_path))
                if not find_pattern_in_text(file_content, self.key_words):
                    logger.info("Key words not found in file %s", file_path)
                    Path(file_path).unlink(missing_ok=True)
                    continue
                file_counter += 1
                logger.info("Key words found in file %s", file_path)
            logger.info(
                "Finished with %d files for process %s after keyword filtering.",
                file_counter,
                process_number,
            )
        self.event_generate("<<CrawlingFinished>>")
        self.destroy()
