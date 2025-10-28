# ================================================================
# [0] Nome: Buscador (Eproc) — GUI + Busca flexível de localizador
# ================================================================
# Requisitos:
#   pip install selenium requests PyPDF2
# Observações:
#   - Usando Opção B: o script ANEXA ao Chrome já aberto com depuração.
#     Abra antes o atalho:
#     "C:\Arquivos de Programas\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\ChromeDebug"
#   - Busca de localizador por TRECHO, sem acentos/caixa; se achar vários,
#     pergunta qual usar.
#   - Filtro de palavras-chave: AND/OR, parênteses, curinga de prefixo '*'.
#     Implementação com parser seguro (sem eval).
#   - Apelação: peças [Sentença, Apelação, Contrarrazões, Parecer MP]
#     Agravo: peça INIC1.
#   - PDFs são baixados temporariamente; só movidos para a pasta final
#     se o filtro aprovar (ou se filtro estiver desativado).

# --------------------------
# [1] Imports e Constantes
# --------------------------
import os, re, sys, time, shutil, tempfile, unicodedata
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
    import PyPDF2  # opcional para leitura de texto de PDFs

    _HAVE_PDF2 = True
except Exception:
    _HAVE_PDF2 = False

URL_LOGIN = "https://eproc2g.tjsc.jus.br/eproc/externo_controlador.php?acao=principal"
CHROME_DRIVER_PATH = (
    r"C:\ChromeDriver\chromedriver.exe"  # mantenha seu chromedriver aqui
)
PASTA_PDFS = Path(r"C:\recursos")
DIR_PRINTS = Path("prints")
DIR_PRINTS.mkdir(exist_ok=True)

# Apelidos (podem ser expandidos à vontade)
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


# -------------------------------------------
# [2] Utilidades: normalização e comparações
# -------------------------------------------
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


# ---------------------------------------
# [3] Selenium helpers (cliques e waits)
# ---------------------------------------
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
    # coleta textos de <td> visíveis (para descobrir localizadores/apelidos)
    vistos, out = set(), []
    for td in driver.find_elements(By.TAG_NAME, "td"):
        t = td.text.strip()
        if t and t not in vistos:
            vistos.add(t)
            out.append(t)
    return out


# ---------------------------------------
# [4] Download e leitura de PDF (seguro)
# ---------------------------------------
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


# --------------------------------------------------------
# [5] Parser SEGURO para filtro: AND/OR, () e curinga '*'
# --------------------------------------------------------
# gramática simples:
#   expr := term (OR term)*
#   term := factor (AND factor)*
#   factor := WORD | '(' expr ')'
#   WORD := letras/números (opcionalmente terminando em '*')
# conectores aceitos: 'e','and','&&' ; 'ou','or','||'  (case-insensitive)
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
            out.append(t)  # termo
    return out


def to_postfix(tokens: List[str]) -> List[str]:
    # shunting-yard: AND tem precedência sobre OR
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
            out.append(tok)  # termo
    while stack:
        out.append(stack.pop())
    return out


def make_matcher(pattern: Optional[str]) -> Callable[[str], bool]:
    if not pattern:  # sem filtro = sempre aprova
        return lambda _text: True
    tokens = tokenize(pattern)
    postfix = to_postfix(tokens)

    def eval_text(text: str) -> bool:
        T = norm(text)
        words = T.split()  # para prefixo

        def term_hit(token: str) -> bool:
            # token pode terminar com * (prefixo)
            if token.endswith("*"):
                pref = token[:-1]
                if not pref:
                    return False
                return any(w.startswith(pref) for w in words)
            else:
                # correspondência por palavra inteira (aproximação com split)
                return f" {token} " in f" {T} "

        stack: List[bool] = []
        for tk in postfix:
            if tk == "AND":
                b = stack.pop()
                a = stack.pop()
                stack.append(a and b)
            elif tk == "OR":
                b = stack.pop()
                a = stack.pop()
                stack.append(a or b)
            else:
                stack.append(term_hit(tk))
        return bool(stack and stack[-1])

    return eval_text


# ----------------------------------------------------
# [6] GUI: coleta config e confirmação de localizador
# ----------------------------------------------------
import tkinter as tk
from tkinter import simpledialog, messagebox


def gui_get_config() -> Tuple[str, str, List[str], Optional[str], bool]:
    root = tk.Tk()
    root.withdraw()
    loc_hint = simpledialog.askstring(
        "Buscador — Localizador",
        "Digite um TRECHO do localizador (ex.: 'Duda' ou '0.06 Duda'):",
        initialvalue="Duda",
    )
    if not loc_hint:
        sys.exit("Cancelado.")
    tipo = simpledialog.askstring(
        "Buscador — Tipo de recurso", "Apelação ou Agravo?", initialvalue="Apelação"
    )
    if not tipo:
        sys.exit("Cancelado.")
    tipo = tipo.strip().lower()
    if tipo.startswith("ap"):
        # peças de apelação
        pecas_str = simpledialog.askstring(
            "Buscador — Peças de apelação",
            "Quais peças? Opções: Sentenca, Apelacao, Contrarazoes, Parecer\n"
            "Separe por vírgula. Deixe vazio para 'Apelacao' apenas.",
            initialvalue="Apelacao",
        )
        pecas = (
            ["apelacao"]
            if not (pecas_str and pecas_str.strip())
            else [norm(p).replace("ç", "c") for p in pecas_str.split(",") if p.strip()]
        )
    else:
        tipo = "agravo"
        pecas = ["inic1"]

    patt = simpledialog.askstring(
        "Buscador — Palavras-chave (opcional)",
        "Use AND/OR (ou 'e'/'ou'), parênteses e curinga de prefixo '*'.\n"
        "Exemplo: (casa ou gato) e piz*\n"
        "Deixe vazio para salvar tudo.",
    )
    aplicar = messagebox.askyesno(
        "Buscador — Filtrar?",
        "Aplicar filtragem pelas palavras-chave?\nSe 'Não', salva tudo.",
    )
    root.destroy()
    pattern = patt.strip() if (patt and patt.strip()) else None
    return loc_hint.strip(), tipo, pecas, pattern, aplicar


def gui_choose_localizador(candidatos: List[str]) -> Optional[str]:
    # janela com lista para o usuário escolher 1 localizador
    pick = {"value": None}
    win = tk.Tk()
    win.title("Buscador — Escolha o localizador")
    tk.Label(
        win,
        text="Foram encontrados estes localizadores.\nSelecione um e clique Confirmar:",
    ).pack(padx=8, pady=8)
    lb = tk.Listbox(win, width=60, height=min(12, max(6, len(candidatos))))
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


# --------------------------------------------------
# [7] Navegação: menus e escolha do localizador
# --------------------------------------------------
# --------------------------------------------------
# [7] Navegação: menus e escolha do localizador
# --------------------------------------------------
def navegar_e_escolher_localizador(driver, wait, trecho: str) -> bool:
    # 7.1 Abrir o menu "Localizadores"
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

    # 7.2 Clicar em **Meus Localizadores**
    # (corrigido: NADA de orgão; usar o href correto do TJSC)
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

    # 7.3 Coletar textos da tabela e filtrar pelo trecho digitado
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

    alvo = cand[0] if len(cand) == 1 else gui_choose_localizador(sorted(cand))
    if not alvo:
        print("[INFO] Seleção cancelada.")
        return False

    print(f"[OK] Usando localizador: {alvo}")

    # 7.4 Localiza a linha (tr) do localizador escolhido
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

    # 7.5 Clicar no **número** da coluna “Total de processos”
    # (ajuste fino do XPath: texto numérico puro)
    try:
        link_total = linha.find_element(
            By.XPATH,
            ".//td//a[normalize-space(text())!='' and translate(normalize-space(text()), '0123456789', '')='']",
        )
        clicar_elemento(driver, link_total)
        return True
    except Exception:
        pass

    # 7.6 Fallback: clicar no ícone de consultar (lupa/pasta) na coluna Ações
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
            f"[ERRO] Não consegui entrar no localizador '{alvo}' (número/lupa). Veja {snap.resolve()}"
        )
        return False


# -------------------------------------------------------
# [8] Processamento das peças: Apelação × Agravo (INIC1)
# -------------------------------------------------------
def processar_apelacao(
    driver,
    wait,
    num_proc: str,
    pecas: List[str],
    matcher: Callable[[str], bool],
    aplicar_filtro: bool,
):
    achou_algum = False  # flag global do método

    for peca in pecas:
        aliases = APELIDOS_APELACAO.get(peca, [])
        if not aliases:
            continue

        # 1) TENTATIVA DIRETA: <a>/<span>/<label> contendo o alias (normalizado)
        for alias in aliases:
            alvo = norm(alias)
            try:
                links = driver.find_elements(
                    By.XPATH,
                    (
                        "//*[self::a or self::span or self::label]"
                        "[contains("
                        "translate( translate(normalize-space(.),"
                        "'ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÇàáâãèéêìíòóôõùúç',"
                        "'AAAAEEEIIOOOOUUCaaaaeeeiiioooouuc'),"
                        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ',"
                        "'abcdefghijklmnopqrstuvwxyz'"
                        f"), '{alvo}')]"
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
                if not nova_aba:
                    continue
                driver.switch_to.window(nova_aba[0])
                driver.maximize_window()

                # tenta achar o iframe do PDF
                try:
                    iframe = WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.TAG_NAME, "iframe"))
                    )
                except Exception:
                    print("   - Não achou iframe do PDF.")
                    driver.close()
                    driver.switch_to.window(abas_before[-1])
                    continue

                pdf_url = iframe.get_attribute("src")

                # baixa temporário, aplica filtro, move se aprovado
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp_path = Path(tmp.name)
                try:
                    baixar_pdf_por_cookie(driver, pdf_url, tmp_path)
                except Exception as e:
                    print(f"   - Erro no download: {e}")
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
                        aprovar = matcher(txt)
                    except Exception:
                        aprovar = True

                out_name = f"{peca}_{num_proc}_doc{idx}.pdf".replace("ç", "c")
                destino = PASTA_PDFS / out_name
                if aprovar:
                    shutil.move(str(tmp_path), destino)
                    print(f"      - {peca.capitalize()} {idx} salva: {destino.name}")
                else:
                    tmp_path.unlink(missing_ok=True)
                    print(
                        f"      - {peca.capitalize()} {idx} descartada (filtro não bateu)."
                    )

                driver.close()
                driver.switch_to.window(abas_before[-1])

    # 2) FALLBACK: procurar eventos “APELAÇÃO” e clicar no consultar
    if not achou_algum:
        peca_name = "apelacao"
        try:
            rotulos = driver.find_elements(
                By.XPATH,
                (
                    "//label"
                    "[contains("
                    " translate( translate(normalize-space(.),"
                    " 'ÁÀÂÃÉÊÍÓÔÕÚÇáàâãéêíóôõúç','AAAAEEIOOOUCaaaaeeiooouc'),"
                    " 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),"
                    " 'apelacao')]"
                ),
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
            if not nova_aba:
                continue
            driver.switch_to.window(nova_aba[0])
            driver.maximize_window()

            try:
                iframe = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, "iframe"))
                )
            except Exception:
                print("   - Não achou iframe do PDF (fallback).")
                driver.close()
                driver.switch_to.window(abas_before[-1])
                continue

            pdf_url = iframe.get_attribute("src")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp_path = Path(tmp.name)
            try:
                baixar_pdf_por_cookie(driver, pdf_url, tmp_path)
            except Exception as e:
                print(f"   - Erro no download (fallback): {e}")
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
                    aprovar = matcher(txt)
                except Exception:
                    aprovar = True

            out_name = f"{peca_name}_{num_proc}_doc{r_idx}.pdf".replace("ç", "c")
            destino = PASTA_PDFS / out_name
            if aprovar:
                shutil.move(str(tmp_path), destino)
                print(
                    f"      - {peca_name.capitalize()} {r_idx} salva (fallback): {destino.name}"
                )
            else:
                tmp_path.unlink(missing_ok=True)
                print(
                    f"      - {peca_name.capitalize()} {r_idx} descartada (filtro não bateu, fallback)."
                )

            driver.close()
            driver.switch_to.window(abas_before[-1])


def processar_agravo(
    driver, wait, num_proc: str, matcher: Callable[[str], bool], aplicar_filtro: bool
):
    """
    Captura a PETIÇÃO INICIAL do Agravo.
    Auto-contida: vai à aba Documentos, procura INIC1/variações,
    abre (mesma aba ou nova), baixa o PDF com cookies e aplica o filtro.
    """

    # ---------- helpers locais ----------
    def _goto_docs_tab():
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
                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", el
                )
                el.click()
                time.sleep(0.6)
                return True
            except Exception:
                continue
        return False

    def _abre_inline(link_el) -> Tuple[str, Optional[str]]:
        """Clica no link; se abrir nova aba, troca pra ela. Retorna (handle_origem, handle_nova|None)."""
        handle_origem = driver.current_window_handle
        abas_antes = driver.window_handles[:]
        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", link_el
            )
        except Exception:
            pass
        try:
            WebDriverWait(driver, 12).until(EC.element_to_be_clickable(link_el)).click()
        except Exception:
            try:
                driver.execute_script("arguments[0].click();", link_el)
            except Exception:
                return handle_origem, None

        # esperar nova aba (se houver)
        try:
            WebDriverWait(driver, 5).until(
                lambda d: len(d.window_handles) > len(abas_antes)
            )
            novas = [h for h in driver.window_handles if h not in abas_antes]
            if novas:
                driver.switch_to.window(novas[0])
                driver.maximize_window()
                return handle_origem, novas[0]
        except Exception:
            pass
        return handle_origem, None  # abriu na mesma aba

    def _baixar_do_iframe(idx: int) -> bool:
        try:
            iframe = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "iframe"))
            )
        except Exception:
            print("   - Não achou iframe do PDF da INICIAL.")
            return False

        pdf_url = iframe.get_attribute("src")
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
            return False

        aprovar = True
        if aplicar_filtro and matcher:
            try:
                txt = extrair_texto_pdf(tmp_path)
                aprovar = matcher(txt)
            except Exception:
                aprovar = True

        destino = PASTA_PDFS / f"agravo_{num_proc}_inic{idx}.pdf"
        if aprovar:
            shutil.move(str(tmp_path), destino)
            print(f"      - Petição Inicial {idx} salva: {destino.name}")
            return True
        else:
            tmp_path.unlink(missing_ok=True)
            print(f"      - Petição Inicial {idx} descartada (filtro não bateu).")
            return False

    def _norm_xpath_text():
        # normalizador para busca case-insensitive e sem acentos
        return (
            "translate( translate(normalize-space(.),"
            "'ÁÀÂÃÉÊÍÓÔÕÚÇáàâãéêíóôõúç','AAAAEEIOOOUCaaaaeeiooouuc'),"
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')"
        )

    def _coleta_links(contexto) -> List:
        aliases = [
            "INIC1",
            "INIC 1",
            "PETIÇÃO INICIAL",
            "PETICAO INICIAL",
            "INICIAL",
            "INIC",
        ]
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
                txt = (e.text or "").strip()
                if txt and e not in ach:
                    ach.append(e)
        return ach

    # ---------- 1) Ir para a aba Documentos ----------
    _goto_docs_tab()  # se não der, a busca abaixo ainda pode achar na tela atual

    # ---------- 2) Priorizar INIC1 dentro do evento "Distribuído" ----------
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

    # Fallback: página inteira (Documentos)
    if not links:
        links = _coleta_links(driver)

    if not links:
        print("      - Nenhuma 'Petição Inicial' (INIC1) localizada.")
        return

    # ---------- 3) Abrir cada link e baixar ----------
    salvos = 0
    for idx, link in enumerate(links, start=1):
        handle_volta, handle_nova = _abre_inline(link)

        ok = _baixar_do_iframe(idx)

        # fechar aba nova (se houver) e voltar
        try:
            if handle_nova and handle_nova in driver.window_handles:
                driver.close()
                driver.switch_to.window(handle_volta)
        except Exception:
            pass

        if ok:
            salvos += 1

    if salvos == 0:
        print("      - INICIAL encontrada mas nenhum PDF aprovado/salvo pelo filtro.")


# ----------------------------
# [9] Função principal (main)
# ----------------------------
def main():
    # GUI de configuração
    loc_trecho, tipo_recurso, pecas, pattern, aplicar_filtro = gui_get_config()
    matcher = make_matcher(pattern) if aplicar_filtro else (lambda _t: True)

    print("[CONFIG] Trecho do localizador:", loc_trecho)
    print("[CONFIG] Recurso:", tipo_recurso)
    print("[CONFIG] Peças:", ", ".join(pecas))
    print("[CONFIG] Palavras-chave:", pattern if pattern else "(não)")
    print("[CONFIG] Filtrar:", "Sim" if aplicar_filtro else "Não")

    # Preparos
    PASTA_PDFS.mkdir(parents=True, exist_ok=True)
    if not os.path.exists(CHROME_DRIVER_PATH):
        sys.exit(f"chromedriver não encontrado em {CHROME_DRIVER_PATH}")

    # 🔗 ANEXAR ao Chrome já aberto na porta 9222 (Opção B)
    chrome_opts = ChromeOptions()
    chrome_opts.add_argument("--start-maximized")
    chrome_opts.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

    # prefs de download podem não sobrescrever o perfil já aberto,
    # mas deixamos aqui por compatibilidade
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
        # Se não estiver na página do Eproc, abrimos a URL principal (sem pedir login de novo).
        try:
            cur = (driver.current_url or "").lower()
        except Exception:
            cur = ""
        if "eproc" not in cur:
            driver.get(URL_LOGIN)
            time.sleep(1)

        # Tenta detectar menu principal; se não achar, pede confirmação manual
        try:
            wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//a[contains(.,'Localizador')]")
                )
            )
            print("   → Sessão ativa detectada.")
        except Exception:
            input(
                "➡️  Certifique-se de que o Eproc está logado na janela anexada e pressione ENTER para continuar… "
            )

        print("[2/6] Acessando Localizadores…")
        if not navegar_e_escolher_localizador(driver, wait, loc_trecho):
            return

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

        # loop de processos
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
                # vai para a nova aba (a última costuma ser a do processo)
                for h in driver.window_handles:
                    if h != handle_lista:
                        driver.switch_to.window(h)
                driver.maximize_window()

                if tipo_recurso == "apelação":
                    processar_apelacao(
                        driver, wait, num_proc, pecas, matcher, aplicar_filtro
                    )
                else:
                    processar_agravo(driver, wait, num_proc, matcher, aplicar_filtro)

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

        print("\n[4/6] Finalizado. PDFs em:", PASTA_PDFS.resolve())
        print(
            "   → A janela do Chrome (depuração) permanece aberta e logada para próximos robôs."
        )
        input(
            "✅ Concluído. Pressione ENTER para encerrar o script (o Chrome continuará aberto). "
        )
    finally:
        # NÃO chamamos driver.quit(), para manter a sessão viva pro próximo robô
        try:
            pass
        except Exception:
            pass


# ------------
# [10] Run
# ------------
if __name__ == "__main__":
    main()
