import json

from tkinter import StringVar


class LocatorsMap(StringVar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def set(self, value: dict):
        super().set(json.dumps(value))

    def get(self, key: str | None) -> dict:
        data = json.loads(super().get())
        if key:
            return data.get(key, {})
        return data

    def keys(self) -> list[str]:
        return list(json.loads(super().get()).keys())

    def values(self) -> list[str]:
        return list(json.loads(super().get()).values())

    def items(self) -> list[tuple[str, str]]:
        return list(json.loads(super().get()).items())
