from pathlib import Path


DOMAIN = "https://eproc2g.tjsc.jus.br"

DATA_PATH = Path("data")
STATIC_PATH = DATA_PATH / "static"

STATIC_PATH.mkdir(parents=True, exist_ok=True)
