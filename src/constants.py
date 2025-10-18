from pathlib import Path
import re

DATA_PATH = Path("data")

STATIC_PATH = DATA_PATH / "static"
STATIC_PATH.mkdir(parents=True, exist_ok=True)

CONVERTED_PATH = DATA_PATH / "converted"
CONVERTED_PATH.mkdir(parents=True, exist_ok=True)

DOWNLOADED_PATH = DATA_PATH / "downloaded"

SECRET_PATH = DATA_PATH / "secret.json"
STATE_PATH = DATA_PATH / "state.json"

NAVIGATION_TIMEOUT = 8000 # millisec
ACTION_TIMEOUT = 4000 # millisec

DOMAIN = "https://eproc2g.tjsc.jus.br"
EPROC_PROFILE_SELECTOR = "eproc/externo_controlador.php?acao=entrar_sso"
EPROC_HOME = "/"
EPROC_CONTROLADOR = "/eproc/controlador.php"
EPROC = "/eproc/"

EPROC_PROFILE = "GCIV0801"

PIECES_DOCS_MAPS = {
    "Apelação": re.compile(r"apelação\d*", re.IGNORECASE),
    "Agravo de Instrumento": re.compile(r"inic\d*", re.IGNORECASE),
    "Contra-razões": re.compile(r"contraz(ap)*\d*", re.IGNORECASE),
    "Parecer do Ministério Público": re.compile(r"promoção\d*", re.IGNORECASE),
}
