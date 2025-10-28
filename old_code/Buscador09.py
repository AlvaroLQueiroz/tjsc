# =====================================================================
# Buscador09 (Eproc/SAJ) — LEMBRETES ou PDFs (Apelação/Agravo)
#   • Mantém o que funcionava no Buscador06 ("bruto porém eficaz")
#   • Corrige pontos do Buscador08/09:
#       (1) PDFs: captura robusta da URL real do PDF (iframe/viewer)
#       (2) Lembretes: expansão/aba/iframes + fallback abrindo a CANETA
#       (3) Exporta CSV corretamente (função fora do main)
#   • Organização por blocos numerados para facilitar manutenção
# =====================================================================
# Execução (anexa ao Chrome já aberto):
#   Abra o Chrome ANTES de rodar o script com:
#   "C:\\Arquivos de Programas\\Google\\Chrome\\Application\\chrome.exe"
#       --remote-debugging-port=9222 --user-data-dir="C:\\ChromeDebug"
# =====================================================================

# ------------------------------------------------------------
# [1] Imports, Constantes e Configuração
# ------------------------------------------------------------
import os, re, sys, time, shutil, tempfile, unicodedata, csv, datetime, urllib.parse
from pathlib import Path
from typing import List, Tuple, Optional, Callable, Dict

import requests

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

try:
    import PyPDF2

    _HAVE_PDF2 = True
except Exception:
    _HAVE_PDF2 = False

try:
    import tkinter as tk
    from tkinter import simpledialog, messagebox

    _HAVE_TK = True
except Exception:
    _HAVE_TK = False

URL_LOGIN = "https://eproc2g.tjsc.jus.br/eproc/externo_controlador.php?acao=principal"
CHROME_DRIVER_PATH = r"C:\\ChromeDriver\\chromedriver.exe"
PASTA_PDFS = Path(r"C:\\recursos")
DIR_PRINTS = Path("prints")
DIR_PRINTS.mkdir(exist_ok=True)

# --- [1.1] Apelidos (herdados do 06) ------------------------
APELIDOS_APELACAO: Dict[str, List[str]] = {
    "sentenca": ["SENT", "SENT1", "SENTENÇA", "SENTENCA"],
    "apelacao": ["APELAÇÃO", "APELACAO", "APELAÇÃO1", "APELAÇÃO 1", "APE1"],
    "contrarazoes": ["CONTRAZAP", "CONTRARRAZÕES", "CONTRARRAZOES"],
    "parecer": ["PROMOÇÃO", "PROMOCAO", "PARECER DO MINISTÉRIO PÚBLICO", "PARECER MP"],
}
APELIDOS_AGRAVO: List[str] = [
    "INIC1",
    "PETIÇÃO INICIAL",
    "PETICAO INICIAL",
    "INICIAL",
    "INIC",
]


# ------------------------------------------------------------
# [2] Utilidades de texto (normalização/acentos)
# ------------------------------------------------------------
def strip_accents(s: str) -> str:
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join([c for c in nfkd if not unicodedata.combining(c)])


def norm(s: str) -> str:
    s = strip_accents(s).lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def contains_norm(haystack: str, needle: str) -> bool:
    return norm(needle) in norm(haystack)


# ------------------------------------------------------------
# [3] Selenium helpers (cliques, waits, listagem)
# ------------------------------------------------------------
def clicar_elemento(driver, el) -> None:
    try:
        el.click()
    except Exception:
        driver.execute_script("arguments[0].click();", el)


def localizar_e_clicar_xpath(
    driver, wait, xpaths: List[str], buscar_iframes=True
) -> bool:
    def tenta() -> bool:
        for xp in xpaths:
            try:
                el = wait.until(EC.element_to_be_clickable((By.XPATH, xp)))
                clicar_elemento(driver, el)
                return True
            except Exception:
                continue
        return False

    driver.switch_to.default_content()
    if tenta():
        return True
    if not buscar_iframes:
        return False
    for fr in driver.find_elements(By.TAG_NAME, "iframe"):
        try:
            driver.switch_to.default_content()
            driver.switch_to.frame(fr)
            if tenta():
                return True
        except Exception:
            continue
    driver.switch_to.default_content()
    return False


def listar_textos_tabela(driver) -> List[str]:
    vistos, out = set(), []
    for td in driver.find_elements(By.TAG_NAME, "td"):
        t = td.text.strip()
        if t and t not in vistos:
            vistos.add(t)
            out.append(t)
    return out


# ------------------------------------------------------------
# [4] PDF — Download + Captura ROBUSTA da URL real
# ------------------------------------------------------------
def baixar_pdf_por_cookie(driver, pdf_url: str, destino: Path) -> None:
    sess = requests.Session()
    for cookie in driver.get_cookies():
        sess.cookies.set(cookie["name"], cookie["value"])
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": driver.current_url,
        "Accept": "text/html,application/pdf,*/*",
        "Accept-Language": "pt-BR,pt;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Upgrade-Insecure-Requests": "1",
    }
    with sess.get(pdf_url, headers=headers, timeout=90, stream=True) as r:
        r.raise_for_status()
        with open(destino, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)


def extrair_texto_pdf(arq: Path) -> str:
    if not _HAVE_PDF2:
        return ""
    txt = []
    with arq.open("rb") as f:
        reader = PyPDF2.PdfReader(f)
        for pg in reader.pages:
            try:
                t = pg.extract_text() or ""
                txt.append(t)
            except Exception:
                continue
    return "\n".join(txt)


def _first_iframe_src(driver, wait_timeout=15) -> Optional[str]:
    try:
        iframe = WebDriverWait(driver, wait_timeout).until(
            EC.presence_of_element_located((By.TAG_NAME, "iframe"))
        )
        src = iframe.get_attribute("src")
        return src
    except Exception:
        return None


def _from_viewer_file_param(url: str) -> Optional[str]:
    # Muitos viewers usam viewer.html?file=<URLENCODED_PDF>
    try:
        parsed = urllib.parse.urlparse(url)
        q = urllib.parse.parse_qs(parsed.query)
        if "file" in q and q["file"]:
            return urllib.parse.unquote(q["file"][0])
    except Exception:
        pass
    return None


def capturar_pdf_url_da_aba(driver, wait_timeout=15) -> Optional[str]:
    # 1) Caminho clássico (06): iframe.src
    src = _first_iframe_src(driver, wait_timeout)
    if src:
        if src.lower().startswith("blob:"):
            file_param = _from_viewer_file_param(driver.current_url)
            if file_param and file_param.lower().endswith(".pdf"):
                return file_param
        file_param = _from_viewer_file_param(src)
        if file_param and file_param.lower().endswith(".pdf"):
            return file_param
        if ".pdf" in src.lower():
            return src

    # 2) <object> ou <embed>
    try:
        obj = driver.find_element(
            By.XPATH, "//object[contains(@type,'pdf') or contains(@data,'.pdf')]"
        )
        data = obj.get_attribute("data")
        if data:
            fp = _from_viewer_file_param(data)
            return fp if fp else data
    except Exception:
        pass
    try:
        emb = driver.find_element(
            By.XPATH, "//embed[contains(@type,'pdf') or contains(@src,'.pdf')]"
        )
        e = emb.get_attribute("src")
        if e:
            fp = _from_viewer_file_param(e)
            return fp if fp else e
    except Exception:
        pass

    # 3) URL atual
    try:
        cur = driver.current_url
        if cur:
            fp = _from_viewer_file_param(cur)
            if fp and fp.lower().endswith(".pdf"):
                return fp
            if ".pdf" in cur.lower():
                return cur
    except Exception:
        pass
    return None


# ------------------------------------------------------------
# [5] Query Engine — AND/OR, (), curinga '*', acento-insensível
# ------------------------------------------------------------
def tokenize(pattern: str) -> List[str]:
    s = norm(pattern)
    s = s.replace("(", " ( ").replace(")", " ) ")
    tokens = s.split()
    out = []
    for t in tokens:
        if t in ("e", "and", "&&"):
            out.append("AND")
        elif t in ("ou", "or", "||"):
            out.append("OR")
        elif t in ("(", ")"):
            out.append(t)
        else:
            out.append(t)
    return out


def to_postfix(tokens: List[str]) -> List[str]:
    prec = {"AND": 2, "OR": 1}
    out, stack = [], []
    for tok in tokens:
        if tok in ("AND", "OR"):
            while stack and stack[-1] in prec and prec[stack[-1]] >= prec[tok]:
                out.append(stack.pop())
            stack.append(tok)
        elif tok == "(":
            stack.append(tok)
        elif tok == ")":
            while stack and stack[-1] != "(":
                out.append(stack.pop())
            if stack and stack[-1] == "(":
                stack.pop()
        else:
            out.append(tok)
    while stack:
        out.append(stack.pop())
    return out


def make_matcher(pattern: Optional[str]):
    if not pattern:
        return lambda _t: (True, None)
    tokens = tokenize(pattern)
    postfix = to_postfix(tokens)

    def eval_text(texto: str):
        T = norm(texto)
        first_pos = None

        def find_term_span(token: str):
            nonlocal first_pos
            if token.endswith("*"):
                pref = re.escape(token[:-1])
                m = re.search(r"\b" + pref + r"\w*\b", T)
            else:
                m = re.search(r"\b" + re.escape(token) + r"\b", T)
            if m:
                if first_pos is None:
                    first_pos = m.start()
                return True
            return False

        st = []
        for tk in postfix:
            if tk == "AND":
                b = st.pop()
                a = st.pop()
                st.append(a and b)
            elif tk == "OR":
                b = st.pop()
                a = st.pop()
                st.append(a or b)
            else:
                st.append(find_term_span(tk))
        ok = bool(st and st[-1])
        if ok and first_pos is not None:
            ini = max(0, first_pos - 80)
            fim = min(len(T), first_pos + 80)
            return True, T[ini:fim]
        return ok, None

    return eval_text


# ------------------------------------------------------------
# [6] GUI — pergunta MODO primeiro
# ------------------------------------------------------------
def gui_get_config() -> dict:
    if not _HAVE_TK:
        # fallback via input()
        modo = (
            input("Pesquisar em: LEMBRETES ou PDFs? (Enter=LEMBRETES) ") or "LEMBRETES"
        )
        modo = "PDFs" if norm(modo).startswith("pdf") else "LEMBRETES"
        loc_hint = input("Digite um TRECHO do localizador: ").strip()
        if not loc_hint:
            sys.exit("Cancelado.")
        cfg = {"modo": modo, "loc_hint": loc_hint}
        if modo == "LEMBRETES":
            cores_str = input("Cores (vazio = todas): ").strip()
            cores = (
                [norm(c) for c in cores_str.split(",") if c.strip()]
                if cores_str
                else None
            )
            patt = (
                input("Consulta (AND/OR, (), *). Vazio = sem filtro: ").strip() or None
            )
            aplicar = (
                True
                if input("Aplicar o filtro? (s/N) ").strip().lower() == "s"
                else False
            )
            cfg.update({"cores": cores, "pattern": patt, "aplicar": aplicar})
        else:
            tipo = input("Apelação ou Agravo? ").strip() or "Apelação"
            tipo = "apelação" if norm(tipo).startswith("ap") else "agravo"
            if tipo == "apelação":
                pecas_str = input(
                    "Peças (Sentenca,Apelacao,Contrarazoes,Parecer). Vazio=Apelacao: "
                ).strip()
                pecas = (
                    ["apelacao"]
                    if not pecas_str
                    else [
                        norm(p).replace("ç", "c")
                        for p in pecas_str.split(",")
                        if p.strip()
                    ]
                )
            else:
                pecas = ["inic1"]
            patt = input("Palavras-chave (vazio = salvar tudo): ").strip() or None
            aplicar = (
                True
                if input("Aplicar filtro? (s/N) ").strip().lower() == "s"
                else False
            )
            cfg.update(
                {"tipo": tipo, "pecas": pecas, "pattern": patt, "aplicar": aplicar}
            )
        return cfg

    root = tk.Tk()
    root.withdraw()

    modo = (
        simpledialog.askstring(
            "Buscador — Modo",
            "Pesquisar em: LEMBRETES ou PDFs?\n(Enter = LEMBRETES)",
            initialvalue="LEMBRETES",
        )
        or "LEMBRETES"
    )
    modo = "PDFs" if norm(modo).startswith("pdf") else "LEMBRETES"

    loc_hint = simpledialog.askstring(
        "Buscador — Localizador",
        "Digite um TRECHO do localizador (ex.: 'Duda' ou '0.06 Duda'):",
        initialvalue="Duda",
    )
    if not loc_hint:
        sys.exit("Cancelado.")

    cfg = {"modo": modo, "loc_hint": loc_hint.strip()}

    if modo == "LEMBRETES":
        cores_str = simpledialog.askstring(
            "Buscador — Cores",
            "Quais cores considerar? (amarelo, azul, laranja, verde, vermelho, cinza)\n"
            "Deixe vazio para TODAS.",
            initialvalue="",
        )
        cores = (
            [norm(c) for c in cores_str.split(",") if c.strip()] if cores_str else None
        )
        patt = simpledialog.askstring(
            "Buscador — Consulta (opcional)",
            "Use AND/OR (ou 'e'/'ou'), parênteses e curinga '*'.\n"
            "Ex.: (casa ou carro) e acord* \n"
            "Deixe vazio para não filtrar.",
        )
        aplicar = messagebox.askyesno(
            "Buscador — Filtrar?", "Aplicar a consulta? (Sim/Não)"
        )
        cfg.update(
            {
                "cores": cores,
                "pattern": patt.strip() if (patt and patt.strip()) else None,
                "aplicar": aplicar,
            }
        )
    else:
        tipo = (
            simpledialog.askstring(
                "Buscador — Tipo de recurso",
                "Apelação ou Agravo?",
                initialvalue="Apelação",
            )
            or "Apelação"
        )
        tipo = "apelação" if norm(tipo).startswith("ap") else "agravo"
        if tipo == "apelação":
            pecas_str = simpledialog.askstring(
                "Buscador — Peças de apelação",
                "Quais peças? Opções: Sentenca, Apelacao, Contrarazoes, Parecer\n"
                "Separe por vírgula. Deixe vazio para 'Apelacao'.",
                initialvalue="Apelacao",
            )
            pecas = (
                ["apelacao"]
                if not (pecas_str and pecas_str.strip())
                else [
                    norm(p).replace("ç", "c") for p in pecas_str.split(",") if p.strip()
                ]
            )
        else:
            pecas = ["inic1"]
        patt = simpledialog.askstring(
            "Buscador — Palavras-chave (opcional)",
            "Use AND/OR (ou 'e'/'ou'), parênteses e curinga '*'.\n"
            "Deixe vazio para salvar tudo.",
        )
        aplicar = messagebox.askyesno(
            "Buscador — Filtrar?", "Aplicar filtragem pelas palavras-chave?"
        )
        cfg.update(
            {
                "tipo": tipo,
                "pecas": pecas,
                "pattern": patt.strip() if (patt and patt.strip()) else None,
                "aplicar": aplicar,
            }
        )
    root.destroy()
    return cfg


# ------------------------------------------------------------
# [7] Navegação: abrir localizador escolhido (reuso do 06)
# ------------------------------------------------------------
def navegar_e_escolher_localizador(driver, wait, trecho: str) -> bool:
    # [7.1] Menu
    if not localizar_e_clicar_xpath(
        driver,
        wait,
        [
            "//a[normalize-space()='Localizadores']",
            "//a[contains(.,'Localizador') and not(contains(.,'Config'))]",
            "//li[a[contains(.,'Localizador')]]/a",
        ],
    ):
        snap = DIR_PRINTS / "erro_localizadores.png"
        driver.save_screenshot(str(snap))
        print(f"[ERRO] Menu 'Localizadores' não encontrado. Veja {snap.resolve()}")
        return False
    time.sleep(1)

    # [7.2] Meus Localizadores
    if not localizar_e_clicar_xpath(
        driver,
        wait,
        [
            "//a[normalize-space()='Meus Localizadores']",
            "//a[contains(.,'Meus Localizadores')]",
            "//a[contains(@href,'usuario_tipo_monitoramento_localizador_listar')]",
            "//a[contains(@href,'usuario_localizador_listar')]",
        ],
    ):
        snap = DIR_PRINTS / "erro_meus_localizadores.png"
        driver.save_screenshot(str(snap))
        print(f"[ERRO] Link 'Meus Localizadores' não encontrado. Veja {snap.resolve()}")
        return False
    time.sleep(1)

    # [7.3] Coleta/filtra
    textos = listar_textos_tabela(driver)
    cand = [t for t in textos if contains_norm(t, trecho)]
    if not cand:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        textos = listar_textos_tabela(driver)
        cand = [t for t in textos if contains_norm(t, trecho)]
    if not cand:
        snap = DIR_PRINTS / "erro_localizador.png"
        driver.save_screenshot(str(snap))
        print(f"[ERRO] Nenhum localizador contém '{trecho}'. Veja {snap.resolve()}")
        return False

    # [7.4] Escolha
    def _choose(candidatos: List[str]) -> Optional[str]:
        if not _HAVE_TK:
            # sem Tk: pega o primeiro
            return candidatos[0]
        pick = {"value": None}
        win = tk.Tk()
        win.title("Buscador — Escolha o localizador")
        tk.Label(win, text="Selecione o localizador e clique Confirmar:").pack(
            padx=8, pady=8
        )
        lb = tk.Listbox(win, width=70, height=min(12, max(6, len(candidatos))))
        for c in candidatos:
            lb.insert(tk.END, c)
        lb.pack(padx=8, pady=8)

        def ok():
            if not lb.curselection():
                messagebox.showerror("Buscador", "Selecione um item.")
                return
            pick["value"] = lb.get(lb.curselection()[0])
            win.destroy()

        tk.Button(win, text="Confirmar", command=ok).pack(pady=8)
        win.mainloop()
        return pick["value"]

    alvo = cand[0] if len(cand) == 1 else _choose(sorted(cand))
    if not alvo:
        print("[INFO] Seleção cancelada.")
        return False
    print(f"[OK] Usando localizador: {alvo}")

    # [7.5] Abrir resultados (número Total ou lupa)
    try:
        linha = wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    f"//tr[.//td[normalize-space()='{alvo}'] or .//td[contains(normalize-space(.),\"{alvo}\")]]",
                )
            )
        )
    except Exception:
        snap = DIR_PRINTS / "erro_linha_localizador.png"
        driver.save_screenshot(str(snap))
        print(
            f"[ERRO] Não encontrei a linha do localizador '{alvo}'. Veja {snap.resolve()}"
        )
        return False

    try:
        link_total = linha.find_element(
            By.XPATH,
            ".//td//a[normalize-space(text())!='' and translate(normalize-space(text()), '0123456789', '')='']",
        )
        clicar_elemento(driver, link_total)
        return True
    except Exception:
        pass
    try:
        botao_acao = linha.find_element(
            By.XPATH,
            ".//a[@title and (contains(translate(@title,'LUPAÇÁÍÉÓÚÃÕ','lupaçáióúãõ'),'consultar') or contains(translate(@title,'LUPAÇÁÍÉÓÚÃÕ','lupaçáióúãõ'),'processo'))]",
        )
        clicar_elemento(driver, botao_acao)
        return True
    except Exception:
        snap = DIR_PRINTS / "erro_click_total_ou_lupa.png"
        driver.save_screenshot(str(snap))
        print(
            f"[ERRO] Não consegui entrar no localizador '{alvo}'. Veja {snap.resolve()}"
        )
        return False


# ------------------------------------------------------------
# [8] LEMBRETES — ABA/IFRAMES + fallback abrindo a CANETA (modal)
# ------------------------------------------------------------
def _tentar_clicar_aba_lembretes(driver):
    candidatos = [
        "//a[normalize-space()='Lembretes']",
        "//a[contains(.,'Lembretes') and contains(@class,'aba')]",
        "//a[contains(@href,'lembrete') and contains(@class,'aba')]",
        "//li[a[normalize-space()='Lembretes']]/a",
        "//button[normalize-space()='Lembretes']",
    ]
    for xp in candidatos:
        try:
            el = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            el.click()
            time.sleep(0.4)
            return True
        except Exception:
            continue
    return False


def _expandir_no_contexto(driver) -> bool:
    try:
        fld = WebDriverWait(driver, 2).until(
            EC.presence_of_element_located((By.XPATH, "//fieldset[@id='fldLembretes']"))
        )
    except Exception:
        return False
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", fld)
    except Exception:
        pass
    try:
        style = (fld.get_attribute("style") or "").lower()
        if "display:none" in style or "display: none" in style:
            try:
                leg = fld.find_element(
                    By.XPATH, ".//legend|.//div[contains(@class,'whiteboard-legend')]"
                )
                driver.execute_script("arguments[0].click();", leg)
                time.sleep(0.3)
            except Exception:
                driver.execute_script("arguments[0].style.display='block';", fld)
    except Exception:
        pass
    try:
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//fieldset[@id='fldLembretes']//div[contains(@class,'whiteboard-note')]",
                )
            )
        )
        return True
    except Exception:
        try:
            WebDriverWait(driver, 1).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[contains(@class,'whiteboard-note')]")
                )
            )
            return True
        except Exception:
            return False


def expandir_lembretes(driver, timeout=15) -> bool:
    driver.switch_to.default_content()
    _tentar_clicar_aba_lembretes(driver)
    if _expandir_no_contexto(driver):
        return True
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    for fr in iframes:
        try:
            driver.switch_to.default_content()
            driver.switch_to.frame(fr)
            if _expandir_no_contexto(driver):
                return True
        except Exception:
            continue
    driver.switch_to.default_content()
    return False


def _rgb_to_color_name(r: int, g: int, b: int) -> str:
    if abs(r - g) < 18 and abs(g - b) < 18:
        return "cinza"
    if r > 200 and g < 120 and b < 120:
        return "vermelho"
    if r > 220 and 120 <= g <= 200 and b < 110:
        return "laranja"
    if r > 220 and g > 220 and b < 150:
        return "amarelo"
    if g > 200 and r < 150 and b < 150:
        return "verde"
    if b > 200 or (b > 160 and r < 140 and g < 190):
        return "azul"
    if max(r, g, b) == r:
        return "vermelho"
    if max(r, g, b) == g:
        return "verde"
    return "azul"


def _parse_bgcolor(style_text: str) -> Optional[str]:
    if not style_text:
        return None
    m = re.search(r"background:\s*rgb\((\d+),\s*(\d+),\s*(\d+)\)", style_text)
    if not m:
        m = re.search(r"background-color:\s*rgb\((\d+),\s*(\d+),\s*(\d+)\)", style_text)
    if not m:
        return None
    r, g, b = map(int, m.groups())
    return _rgb_to_color_name(r, g, b)


def _coletar_no_contexto(driver, num_proc, cores_desejadas, matcher, aplicar_filtro):
    registros = []
    notes = driver.find_elements(
        By.XPATH,
        "//fieldset[@id='fldLembretes']//div[contains(@class,'whiteboard-note')]",
    )
    if not notes:
        notes = driver.find_elements(
            By.XPATH, "//div[contains(@class,'whiteboard-note')]"
        )
    for note in notes:
        try:
            style = note.get_attribute("style") or ""
            cor = _parse_bgcolor(style) or "desconhecida"
            if cores_desejadas and cor not in cores_desejadas:
                continue

            def get_txt(xp):
                try:
                    return note.find_element(By.XPATH, xp).text.strip()
                except Exception:
                    return ""

            header = get_txt(".//div[contains(@class,'note-header')]")
            body = get_txt(
                ".//div[contains(@class,'note-text-wrapper') or contains(@class,'note-content')]"
            )
            footer = get_txt(".//div[contains(@class,'note-footer')]")
            texto_integral = "\n".join([t for t in (header, body, footer) if t])
            ok, trecho = (True, None)
            if aplicar_filtro:
                ok, trecho = matcher(texto_integral)
            if ok:
                autor, datahora = "", ""
                m = re.search(
                    r"([a-zA-Z\.\-_]+)\s+(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})",
                    footer,
                )
                if m:
                    autor, datahora = m.group(1), m.group(2)
                registros.append(
                    {
                        "processo": num_proc,
                        "link": driver.current_url,
                        "cor": cor,
                        "autor": autor,
                        "data_hora": datahora,
                        "trecho": trecho or "",
                        "conteudo": texto_integral,
                    }
                )
        except Exception:
            continue
    return registros


def _abrir_modal_edicao_e_ler_texto(driver) -> str | None:
    def _ler_texto_no_contexto() -> Optional[str]:
        try:
            areas = driver.find_elements(By.XPATH, "//textarea")
            melhores = []
            for ta in areas:
                if not ta.is_displayed():
                    continue
                val = (
                    ta.get_attribute("value")
                    or ta.get_attribute("textContent")
                    or ta.text
                    or ""
                ).strip()
                if val:
                    melhores.append(val)
            if melhores:
                return max(melhores, key=len)
        except Exception:
            pass
        try:
            cand = driver.find_elements(
                By.XPATH,
                "//textarea[contains(@id,'Descricao') or contains(@id,'descricao') or "
                "contains(@name,'Descricao') or contains(@name,'descricao')]",
            )
            for ta in cand:
                val = (
                    ta.get_attribute("value")
                    or ta.get_attribute("textContent")
                    or ta.text
                    or ""
                ).strip()
                if val:
                    return val
        except Exception:
            pass
        try:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for fr in iframes:
                try:
                    driver.switch_to.frame(fr)
                    body_text = driver.execute_script(
                        "return (document && document.body && document.body.innerText) || '';"
                    )
                    driver.switch_to.parent_frame()
                    if body_text and body_text.strip():
                        return body_text.strip()
                except Exception:
                    driver.switch_to.parent_frame()
                    continue
        except Exception:
            pass
        return None

    texto = None
    t0 = time.time()
    while time.time() - t0 < 8 and not texto:
        driver.switch_to.default_content()
        texto = _ler_texto_no_contexto()
        if not texto:
            time.sleep(0.4)

    try:
        driver.switch_to.default_content()
        for xp in [
            "//button[normalize-space()='Fechar']",
            "//a[normalize-space()='Fechar']",
            "//input[@value='Fechar']",
            "//button[contains(@onclick,'fechar') or contains(@class,'fechar')]",
            "//div[contains(@class,'modal')]//button[contains(@class,'close')]",
        ]:
            btns = driver.find_elements(By.XPATH, xp)
            if btns:
                try:
                    driver.execute_script("arguments[0].click();", btns[0])
                    break
                except Exception:
                    pass
    except Exception:
        pass
    return texto


def _coletar_via_edicao(
    driver, num_proc: str, cores_desejadas, matcher, aplicar_filtro
) -> list[dict]:
    registros = []
    botoes = driver.find_elements(
        By.XPATH,
        "//div[contains(@class,'whiteboard') and contains(@class,'note')]"
        "//a[.//i[contains(@class,'fa-pencil')]] | "
        "//div[contains(@class,'whiteboard') and contains(@class,'note')]"
        "//a[contains(@title,'Alterar') or contains(translate(@title,'ALTERAR','alterar'),'alterar')] | "
        "//a[contains(@href,'processo_lembrete_destino_alterar')]",
    )
    if not botoes:
        return registros

    for btn in botoes:
        try:
            try:
                card = btn.find_element(
                    By.XPATH,
                    ".//ancestor::div[contains(@class,'whiteboard') and contains(@class,'note')][1]",
                )
            except Exception:
                try:
                    card = btn.find_element(
                        By.XPATH, ".//ancestor::div[contains(@style,'background')][1]"
                    )
                except Exception:
                    card = None

            cor = "desconhecida"
            footer_txt = ""
            if card is not None:
                style = card.get_attribute("style") or ""
                c = _parse_bgcolor(style)
                if c:
                    cor = c
                try:
                    footer_txt = card.find_element(
                        By.XPATH, ".//div[contains(@class,'note-footer')]"
                    ).text
                except Exception:
                    footer_txt = card.text

            try:
                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", btn
                )
            except Exception:
                pass
            try:
                WebDriverWait(driver, 6).until(EC.element_to_be_clickable(btn)).click()
            except Exception:
                try:
                    driver.execute_script("arguments[0].click();", btn)
                except Exception:
                    continue

            texto = _abrir_modal_edicao_e_ler_texto(driver) or ""
            if not texto:
                continue

            ok, trecho = (True, None)
            if aplicar_filtro:
                ok, trecho = matcher(texto)
            if not ok:
                continue

            autor, datahora = "", ""
            m = re.search(
                r"([a-zA-Z\.\-_]+)\s+(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})",
                footer_txt or "",
            )
            if m:
                autor, datahora = m.group(1), m.group(2)

            registros.append(
                {
                    "processo": num_proc,
                    "link": driver.current_url,
                    "cor": cor,
                    "autor": autor,
                    "data_hora": datahora,
                    "trecho": trecho or "",
                    "conteudo": texto,
                }
            )
        except Exception:
            continue
    return registros


def coletar_lembretes(
    driver,
    wait,
    num_proc: str,
    cores_desejadas: Optional[List[str]],
    matcher: Callable[[str], Tuple[bool, Optional[str]]],
    aplicar_filtro: bool,
) -> List[Dict]:
    registros: List[Dict] = []

    expanded = expandir_lembretes(driver, timeout=15)
    if not expanded:
        print("   → Seção Lembretes não visível/expandida (tentaremos mesmo assim).")

    driver.switch_to.default_content()
    regs_doc = _coletar_no_contexto(
        driver, num_proc, cores_desejadas, matcher, aplicar_filtro
    )
    registros.extend(regs_doc)

    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    for fr in iframes:
        try:
            driver.switch_to.default_content()
            driver.switch_to.frame(fr)
            regs_if = _coletar_no_contexto(
                driver, num_proc, cores_desejadas, matcher, aplicar_filtro
            )
            registros.extend(regs_if)
        except Exception:
            continue
    driver.switch_to.default_content()

    if not registros:
        regs_edit = _coletar_via_edicao(
            driver, num_proc, cores_desejadas, matcher, aplicar_filtro
        )
        registros.extend(regs_edit)
        if not regs_edit:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for fr in iframes:
                try:
                    driver.switch_to.default_content()
                    driver.switch_to.frame(fr)
                    regs_if = _coletar_via_edicao(
                        driver, num_proc, cores_desejadas, matcher, aplicar_filtro
                    )
                    registros.extend(regs_if)
                except Exception:
                    continue
            driver.switch_to.default_content()

    print(f"   → Lembretes encontrados (todos os contextos): {len(registros)}")
    return registros


# ------------------------------------------------------------
# [8.x] Exportar CSV (fora do main)
# ------------------------------------------------------------
def exportar_lembretes_csv(
    registros: List[Dict], localizador_nome: str
) -> Optional[Path]:
    if not registros:
        return None
    PASTA_PDFS.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    arq = PASTA_PDFS / f"lembretes_hits_{ts}.csv"
    campos = [
        "processo",
        "link",
        "localizador",
        "cor",
        "autor",
        "data_hora",
        "trecho",
        "conteudo",
        "data_coleta",
    ]
    with arq.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
        w.writeheader()
        agora = datetime.datetime.now().isoformat(timespec="seconds")
        for r in registros:
            w.writerow(
                {
                    "processo": r.get("processo", ""),
                    "link": r.get("link", ""),
                    "localizador": localizador_nome,
                    "cor": r.get("cor", ""),
                    "autor": r.get("autor", ""),
                    "data_hora": r.get("data_hora", ""),
                    "trecho": (r.get("trecho", "") or "").replace("\n", "  "),
                    "conteudo": (r.get("conteudo", "") or "").replace("\n", "  "),
                    "data_coleta": agora,
                }
            )
    return arq


# ------------------------------------------------------------
# [9] PDFs — Apelação e Agravo (INIC1) com capturador robusto
# ------------------------------------------------------------
def _norm_xpath_text():
    return (
        "translate( translate(normalize-space(.),"
        "'ÁÀÂÃÉÊÍÓÔÕÚÇáàâãéêíóôõúç','AAAAEEIOOOUCaaaaeeiooouuc'),"
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')"
    )


def processar_apelacao(
    driver,
    wait,
    num_proc: str,
    pecas: List[str],
    matcher: Callable[
        [
            str,
        ],
        Tuple[bool, Optional[str]],
    ],
    aplicar_filtro: bool,
):
    achou_algum = False

    for peca in pecas:
        aliases = APELIDOS_APELACAO.get(peca, [])
        if not aliases:
            continue

        # [9.1] TENTATIVA DIRETA (bruta/06)
        for alias in aliases:
            alvo = norm(alias)
            try:
                links = driver.find_elements(
                    By.XPATH,
                    (
                        "//*[self::a or self::span or self::label]"
                        f"[contains({_norm_xpath_text()}, '{alvo}')]"
                    ),
                )
            except Exception:
                links = []

            if links:
                achou_algum = True

            for idx, link in enumerate(links, start=1):
                abas_before = driver.window_handles.copy()
                clicar_elemento(driver, link)
                time.sleep(1)
                abas_after = driver.window_handles
                nova_aba = [a for a in abas_after if a not in abas_before]
                if nova_aba:
                    driver.switch_to.window(nova_aba[0])
                    driver.maximize_window()

                pdf_url = capturar_pdf_url_da_aba(driver, wait_timeout=15)
                if not pdf_url:
                    pdf_url = _first_iframe_src(driver, wait_timeout=8)
                    if pdf_url:
                        alt = _from_viewer_file_param(pdf_url)
                        if alt:
                            pdf_url = alt

                if not pdf_url:
                    if nova_aba:
                        driver.close()
                        driver.switch_to.window(abas_before[-1])
                    continue

                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp_path = Path(tmp.name)
                try:
                    baixar_pdf_por_cookie(driver, pdf_url, tmp_path)
                except Exception as e:
                    print(f"   - Erro no download: {e}")
                    if nova_aba:
                        driver.close()
                        driver.switch_to.window(abas_before[-1])
                    try:
                        tmp_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                    continue

                aprovar = True
                if aplicar_filtro and matcher:
                    try:
                        txt = extrair_texto_pdf(tmp_path)
                        aprovar, _ = matcher(txt)
                    except Exception:
                        aprovar = True

                out_name = f"{peca}_{num_proc}_doc{idx}.pdf".replace("ç", "c")
                destino = PASTA_PDFS / out_name
                if aprovar:
                    shutil.move(str(tmp_path), destino)
                    print(f"      - {peca.capitalize()} {idx} salva: {destino.name}")
                else:
                    tmp_path.unlink(missing_ok=True)
                    print(f"      - {peca.capitalize()} {idx} descartada (filtro).")

                if nova_aba:
                    driver.close()
                    driver.switch_to.window(abas_before[-1])

    # [9.2] FALLBACK: evento “APELAÇÃO” → botão consultar
    if not achou_algum:
        try:
            rotulos = driver.find_elements(
                By.XPATH, f"//label[contains({_norm_xpath_text()}, 'apelacao')]"
            )
        except Exception:
            rotulos = []

        for r_idx, rot in enumerate(rotulos, start=1):
            try:
                linha_evento = rot.find_element(By.XPATH, "./ancestor::tr")
                botao_consultar = linha_evento.find_element(
                    By.XPATH, ".//img[contains(@src,'consultar')]/parent::a"
                )
            except Exception:
                continue

            abas_before = driver.window_handles.copy()
            clicar_elemento(driver, botao_consultar)
            time.sleep(1)
            abas_after = driver.window_handles
            nova_aba = [a for a in abas_after if a not in abas_before]
            if nova_aba:
                driver.switch_to.window(nova_aba[0])
                driver.maximize_window()

            pdf_url = capturar_pdf_url_da_aba(driver, wait_timeout=15)
            if not pdf_url:
                pdf_url = _first_iframe_src(driver, wait_timeout=8)
                if pdf_url:
                    alt = _from_viewer_file_param(pdf_url)
                    if alt:
                        pdf_url = alt

            if not pdf_url:
                if nova_aba:
                    driver.close()
                    driver.switch_to.window(abas_before[-1])
                continue

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp_path = Path(tmp.name)
            try:
                baixar_pdf_por_cookie(driver, pdf_url, tmp_path)
            except Exception as e:
                print(f"   - Erro no download (fallback): {e}")
                if nova_aba:
                    driver.close()
                    driver.switch_to.window(abas_before[-1])
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass
                continue

            aprovar = True
            if aplicar_filtro and matcher:
                try:
                    txt = extrair_texto_pdf(tmp_path)
                    aprovar, _ = matcher(txt)
                except Exception:
                    aprovar = True

            destino = PASTA_PDFS / f"apelacao_{num_proc}_doc{r_idx}.pdf"
            if aprovar:
                shutil.move(str(tmp_path), destino)
                print(f"      - Apelação {r_idx} salva (fallback): {destino.name}")
            else:
                tmp_path.unlink(missing_ok=True)
                print(f"      - Apelação {r_idx} descartada (filtro).")

            if nova_aba:
                driver.close()
                driver.switch_to.window(abas_before[-1])


def processar_agravo(
    driver,
    wait,
    num_proc: str,
    matcher: Callable[[str], Tuple[bool, Optional[str]]],
    aplicar_filtro: bool,
):
    # --- [9.3.1] Ir para aba Documentos (se existir) ---------
    xps = [
        "//a[normalize-space()='Documentos']",
        "//a[contains(.,'Documentos Principais')]",
        "//a[contains(.,'Documentos do Processo')]",
        "//a[contains(@href,'documento') and contains(@class,'aba')]",
    ]
    for xp in xps:
        try:
            el = WebDriverWait(driver, 6).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            el.click()
            time.sleep(0.5)
            break
        except Exception:
            continue

    # --- [9.3.2] Coletar links para INIC1/Petição Inicial ----
    def _coleta_links(contexto) -> List:
        aliases = APELIDOS_AGRAVO
        ach = []
        for alias in aliases:
            alvo = norm(alias)
            try:
                encontrados = contexto.find_elements(
                    By.XPATH,
                    (
                        ".//*[self::a or self::span or self::label]"
                        f"[contains({_norm_xpath_text()}, '{alvo}')]"
                    ),
                )
            except Exception:
                encontrados = []
            for e in encontrados:
                if e not in ach:
                    ach.append(e)
        return ach

    try:
        painels = driver.find_elements(
            By.XPATH, f"//*[contains({_norm_xpath_text()}, 'distribuido')]"
        )
    except Exception:
        painels = []

    links = []
    for cont in painels:
        for el in _coleta_links(cont):
            if el not in links:
                links.append(el)
    if not links:
        links = _coleta_links(driver)
    if not links:
        print("      - Nenhuma 'Petição Inicial' (INIC1) localizada.")
        return

    # --- [9.3.3] Abrir e baixar --------------------------------
    salvos = 0
    for idx, link in enumerate(links, start=1):
        handle_origem = driver.current_window_handle
        abas_antes = driver.window_handles[:]
        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", link
            )
        except Exception:
            pass
        try:
            WebDriverWait(driver, 12).until(EC.element_to_be_clickable(link)).click()
        except Exception:
            try:
                driver.execute_script("arguments[0].click();", link)
            except Exception:
                continue

        # troca de aba (se abriu nova)
        try:
            WebDriverWait(driver, 5).until(
                lambda d: len(d.window_handles) > len(abas_antes)
            )
            novas = [h for h in driver.window_handles if h not in abas_antes]
            if novas:
                driver.switch_to.window(novas[0])
                driver.maximize_window()
        except Exception:
            pass

        pdf_url = capturar_pdf_url_da_aba(driver, wait_timeout=15)
        if not pdf_url:
            pdf_url = _first_iframe_src(driver, wait_timeout=8)
            if pdf_url:
                alt = _from_viewer_file_param(pdf_url)
                if alt:
                    pdf_url = alt

        if not pdf_url:
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(handle_origem)
            continue

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp_path = Path(tmp.name)
        try:
            baixar_pdf_por_cookie(driver, pdf_url, tmp_path)
        except Exception as e:
            print(f"   - Erro no download da INICIAL: {e}")
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(handle_origem)
            continue

        aprovar = True
        if aplicar_filtro and matcher:
            try:
                txt = extrair_texto_pdf(tmp_path)
                aprovar, _ = matcher(txt)
            except Exception:
                aprovar = True

        destino = PASTA_PDFS / f"agravo_{num_proc}_inic{idx}.pdf"
        if aprovar:
            shutil.move(str(tmp_path), destino)
            print(f"      - Petição Inicial {idx} salva: {destino.name}")
            salvos += 1
        else:
            tmp_path.unlink(missing_ok=True)
            print(f"      - Petição Inicial {idx} descartada (filtro).")

        if len(driver.window_handles) > 1:
            driver.close()
            driver.switch_to.window(handle_origem)

    if salvos == 0:
        print("      - INICIAL encontrada mas nenhum PDF aprovado/salvo pelo filtro.")


# ------------------------------------------------------------
# [10] main — fluxo unificado
# ------------------------------------------------------------
def main():
    # [10.1] GUI
    cfg = gui_get_config()
    modo = cfg["modo"]
    loc_trecho = cfg["loc_hint"]
    print("[CONFIG] Modo:", modo)
    print("[CONFIG] Localizador:", loc_trecho)

    if modo == "LEMBRETES":
        cores = cfg["cores"]
        pattern = cfg["pattern"]
        aplicar = cfg["aplicar"]
        matcher = make_matcher(pattern)
        print("[CONFIG] Cores:", ", ".join(cores) if cores else "(todas)")
        print("[CONFIG] Consulta:", pattern if pattern else "(não)")
        print("[CONFIG] Filtrar:", "Sim" if aplicar else "Não")
    else:
        tipo = cfg["tipo"]
        pecas = cfg["pecas"]
        pattern = cfg["pattern"]
        aplicar = cfg["aplicar"]
        matcher = make_matcher(pattern)
        print("[CONFIG] Recurso:", tipo)
        print("[CONFIG] Peças:", ", ".join(pecas))
        print("[CONFIG] Palavras-chave:", pattern if pattern else "(não)")
        print("[CONFIG] Filtrar:", "Sim" if aplicar else "Não")

    # [10.2] Driver
    PASTA_PDFS.mkdir(parents=True, exist_ok=True)
    if not os.path.exists(CHROME_DRIVER_PATH):
        sys.exit(f"chromedriver não encontrado em {CHROME_DRIVER_PATH}")

    chrome_opts = ChromeOptions()
    chrome_opts.add_argument("--start-maximized")
    chrome_opts.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    prefs = {
        "download.default_directory": str(PASTA_PDFS.resolve()),
        "download.prompt_for_download": False,
        "plugins.always_open_pdf_externally": True,
    }
    chrome_opts.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(
        service=ChromeService(executable_path=CHROME_DRIVER_PATH), options=chrome_opts
    )
    wait = WebDriverWait(driver, 30)

    try:
        print("[1/6] Verificando sessão no Eproc…")
        try:
            cur = (driver.current_url or "").lower()
        except Exception:
            cur = ""
        if "eproc" not in cur:
            driver.get(URL_LOGIN)
            time.sleep(1)
        try:
            wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//a[contains(.,'Localizador')]")
                )
            )
            print("   → Sessão ativa detectada.")
        except Exception:
            input("➡️  Faça login no Eproc na janela anexada e pressione ENTER… ")

        print("[2/6] Acessando Localizadores…")
        if not navegar_e_escolher_localizador(driver, wait, loc_trecho):
            return

        # Nome do localizador (se houver cabeçalho)
        try:
            localizador_nome = wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//*[contains(@class,'infraAreaDados')]//h1|//h2|//h3")
                )
            ).text.strip()
        except Exception:
            localizador_nome = loc_trecho

        print("[3/6] Carregando lista de processos…")
        try:
            wait.until(
                EC.presence_of_all_elements_located(
                    (By.XPATH, "//a[contains(@href,'num_processo=')]")
                )
            )
        except Exception:
            snap = DIR_PRINTS / "erro_sem_processos.png"
            driver.save_screenshot(str(snap))
            print(f"[ERRO] Nenhum processo encontrado. Veja {snap.resolve()}")
            return

        linhas = driver.find_elements(
            By.XPATH, "//tr[.//a[contains(@href,'num_processo=')]]"
        )
        print(f"   → {len(linhas)} processo(s) listado(s).")

        registros_lembretes: List[Dict] = []

        # [10.3] Loop processos
        for linha in linhas:
            try:
                link_proc = linha.find_element(
                    By.XPATH, ".//a[contains(@href,'num_processo=')]"
                )
                num_proc = link_proc.text.strip().replace(".", "").replace("-", "")
                try:
                    classe = linha.find_element(
                        By.XPATH,
                        ".//span[contains(@class,'span-classe-judicial-contraste')]",
                    ).text.strip()
                except Exception:
                    classe = ""
                print(f"\n[Processo {num_proc}] Classe: {classe}")

                handle_lista = driver.current_window_handle
                ActionChains(driver).key_down(Keys.CONTROL).click(link_proc).key_up(
                    Keys.CONTROL
                ).perform()
                time.sleep(1)
                for h in driver.window_handles:
                    if h != handle_lista:
                        driver.switch_to.window(h)
                driver.maximize_window()

                if modo == "LEMBRETES":
                    regs = coletar_lembretes(
                        driver,
                        wait,
                        num_proc,
                        cfg.get("cores"),
                        matcher,
                        cfg.get("aplicar"),
                    )
                    if regs:
                        registros_lembretes.extend(regs)
                        print(f"   → {len(regs)} lembrete(s) compatível(is).")
                    else:
                        print("   → Nenhum lembrete compatível.")
                else:
                    if cfg["tipo"] == "apelação":
                        processar_apelacao(
                            driver,
                            wait,
                            num_proc,
                            cfg["pecas"],
                            matcher,
                            cfg["aplicar"],
                        )
                    else:
                        processar_agravo(
                            driver, wait, num_proc, matcher, cfg["aplicar"]
                        )

                driver.close()
                driver.switch_to.window(handle_lista)
            except Exception as e:
                print(f"   - Erro ao processar processo: {e}")
                try:
                    if len(driver.window_handles) > 1:
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                except Exception:
                    pass

        # [10.4] Saída
        if modo == "LEMBRETES":
            print(
                f"\n[4/6] Total de lembretes compatíveis (agregado): {len(registros_lembretes)}"
            )
            if registros_lembretes:
                arq = exportar_lembretes_csv(registros_lembretes, localizador_nome)
                print(f"[5/6] CSV gerado: {arq.resolve()}")
            else:
                print("[5/6] Nenhum lembrete compatível → CSV não gerado.")
        else:
            print("\n[4/6] Fluxo PDFs concluído. Arquivos em:", PASTA_PDFS.resolve())

        input("✅ Concluído. ENTER para encerrar (o Chrome em depuração fica aberto). ")
    finally:
        pass


# ------------------------------------------------------------
# [11] Run
# ------------------------------------------------------------
if __name__ == "__main__":
    main()
