import json

from tkinter import StringVar
from typing import Any


class DictVar(StringVar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__class__.bla = str

    def set(self, value: dict):
        super().set(json.dumps(value))

    def get(self, key: str = "") -> dict[str, Any]:
        data = json.loads(super().get())
        if key:
            return data.get(key, {})
        return data

    def keys(self) -> list[str]:
        return list(self.get().keys())

    def values(self) -> list[str]:
        return list(self.get().values())

    def items(self) -> list[tuple[str, Any]]:
        return list(self.get().items())
