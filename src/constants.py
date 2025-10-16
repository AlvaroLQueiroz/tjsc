from pathlib import Path


DATA_PATH = Path("data")

STATIC_PATH = DATA_PATH / "static"
STATIC_PATH.mkdir(parents=True, exist_ok=True)

CONVERTED_PATH = DATA_PATH / "converted"
CONVERTED_PATH.mkdir(parents=True, exist_ok=True)

SECRET_PATH = DATA_PATH / "secret.json"
STATE_PATH = DATA_PATH / "state.json"

NAVIGATION_TIMEOUT = 2000 # millisec
ACTION_TIMEOUT = 3000 # millisec

DOMAIN = "https://eproc2g.tjsc.jus.br"
EPROC_HOME = "/eproc/index.php"
EPROC_CONTROLADOR = "/eproc/controlador.php"


EPROC_PROFILE = "emanuelamaral / MAGISTRADO / GCIV0801"
