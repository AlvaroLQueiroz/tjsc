import tkinter as tk
from tkinter import ttk

from src.interface.logo import LogoTitle
from src.query_language import query


class SelectParametersFrame(ttk.Frame):
    def __init__(self, parent, locators: list[str], pieces: list[str]):
        super().__init__(parent)
        self.locators = locators
        self.pieces = pieces

        self.selected_locator = tk.StringVar(value=self.locators[0] if self.locators else "")
        self.selected_piece = tk.StringVar(value=self.pieces[0] if self.pieces else "")
        self.selected_key_words = tk.StringVar()

        self.logo = LogoTitle(self)
        self.logo.pack(fill="y", pady=20)

        self.locator_label = ttk.Label(self, text="Selecione o localizador:")
        self.locator_label.pack(pady=5)
        self.locator_combobox = ttk.Combobox(self, textvariable=self.selected_locator, values=self.locators)
        self.locator_combobox.pack(pady=5)

        self.piece_label = ttk.Label(self, text="Tipo de peça:")
        self.piece_label.pack(pady=5)
        self.piece_combobox = ttk.Combobox(self, textvariable=self.selected_piece, values=self.pieces)
        self.piece_combobox.pack(pady=5)

        self.key_words_label = ttk.Label(self, text="Palavras-chave:")
        self.key_words_label.pack(pady=5)
        self.key_words_entry = ttk.Entry(self, textvariable=self.selected_key_words)
        self.key_words_entry.pack(pady=5)

        self.button = ttk.Button(self, text="Confirmar", command=self.confirm)
        self.button.bind("<Return>", self.confirm)
        self.button.pack(pady=5)

        self.error_label = ttk.Label(self, text="Error ao fazer login.", foreground="red")

    def confirm(self, *args):
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

        is_key_words_valid, _ = query.run_tests(key_words, print_results=False, failure_tests=False)
        if not is_key_words_valid:
            self.error_label.config(text="Palavras-chave inválidas.")
            self.error_label.pack(pady=5)
            return

        self.event_generate("<<ParametersSelected>>")
