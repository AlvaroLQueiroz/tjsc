import tkinter as tk
from tkinter import ttk

from async_tkinter_loop import async_handler
from playwright.async_api import BrowserContext, Page

from src.constants import PIECES_DOCS_MAPS
from src.crawler.locator import get_my_locators
from src.dto import DictVar
from src.interface.loading import LoadingFrame
from src.interface.logo import LogoTitle
from src.query_language import query


class SelectParametersPage(ttk.Frame):
    PIECES_KEYS = list(PIECES_DOCS_MAPS.keys())

    def __init__(self, parent: tk.Tk, page: Page, context: BrowserContext):
        super().__init__(parent)
        self.page = page
        self.context = context

        self.locators = DictVar(value={})
        self.locators.trace_add("write", self.on_locators_change)
        self.selected_locator = tk.StringVar(value="")
        self.selected_piece = tk.StringVar(value=self.PIECES_KEYS[0])
        self.selected_key_words = tk.StringVar(value="")

        self.build_ui()
        self.get_user_locators()

    def build_ui(self):
        self.logo = LogoTitle(self)
        self.loading_frame = LoadingFrame(self, text="Carregando localizadores...")

        self.locator_label = ttk.Label(self, text="Selecione o localizador:")
        self.locator_combobox = ttk.Combobox(self, textvariable=self.selected_locator)

        self.piece_label = ttk.Label(self, text="Tipo de peça:")
        self.piece_combobox = ttk.Combobox(self, textvariable=self.selected_piece, values=list(PIECES_DOCS_MAPS.keys()))

        self.key_words_label = ttk.Label(self, text="Palavras-chave:")
        self.key_words_entry = ttk.Entry(self, textvariable=self.selected_key_words)

        self.button = ttk.Button(self, text="Confirmar", command=self.handle_submit)
        self.button.bind("<Return>", self.handle_submit)

        self.error_label = ttk.Label(self, text="Error ao fazer login.", foreground="red")

    def show(self):
        self.logo.pack(fill="y", pady=20)
        self.locator_label.pack(pady=5)
        self.locator_combobox.pack(pady=5)
        self.piece_label.pack(pady=5)
        self.piece_combobox.pack(pady=5)
        self.key_words_label.pack(pady=5)
        self.key_words_entry.pack(pady=5)
        self.button.pack(pady=5)

    def hide(self):
        self.logo.pack_forget()
        self.locator_combobox.pack_forget()
        self.piece_combobox.pack_forget()
        self.key_words_entry.pack_forget()
        self.button.pack_forget()
        self.error_label.pack_forget()

    def get_user_locators(self, *args):
        self.loading_frame.pack(fill="both", expand=True)
        async_handler(get_my_locators)(self.page, self.locators.set)

    def on_locators_change(self, *args):
        locators = self.locators.get()
        locator_names = list(locators.keys())
        self.selected_locator.set(locator_names[0] if locator_names else "")
        self.locator_combobox.config(values=locator_names)
        self.loading_frame.pack_forget()
        self.show()

    def handle_submit(self, *args):
        self.error_label.pack_forget()
        locator = self.selected_locator.get()
        piece = self.selected_piece.get()
        key_words = self.selected_key_words.get()
        if not locator:
            self.error_label.config(text="Por favor, selecione um localizador.")
            self.error_label.pack(pady=5)
            return
        elif not piece:
            self.error_label.config(text="Por favor, selecione um tipo de peça.")
            self.error_label.pack(pady=5)
            return
        elif not key_words:
            self.error_label.config(text="Por favor, preencha todos os campos.")
            self.error_label.pack(pady=5)
            return

        self.loading_frame.pack(fill="both", expand=True)

        is_key_words_valid, _ = query.run_tests(key_words, print_results=False, failure_tests=False)
        if not is_key_words_valid:
            self.loading_frame.pack_forget()
            self.error_label.config(text="Palavras-chave inválidas.")
            self.error_label.pack(pady=5)
            return

        self.event_generate("<<ParametersSelected>>", data={
            "locator": locator,
            "piece": piece,
            "key_words": key_words})
        self.destroy()
