# ------------------------------------------------------------
# [8] LEMBRETES — ABA/IFRAMES + fallback abrindo a CANETA (modal ou página)
# ------------------------------------------------------------
def _tentar_clicar_aba_lembretes(driver):
    candidatos = [
        "//a[normalize-space()='Lembretes']",
        "//a[contains(.,'Lembretes') and contains(@class,'aba')]",
        "//a[contains(@href,'lembrete') and contains(@class,'aba')]",
        "//li[a[normalize-space()='Lembretes']]/a",
        "//button[normalize-space()='Lembretes']",
        "//span[normalize-space()='Lembretes']/ancestor::a",
    ]
    for xp in candidatos:
        try:
            el = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH, xp)))
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
                leg = fld.find_element(By.XPATH, ".//legend|.//div[contains(@class,'whiteboard-legend')]")
                driver.execute_script("arguments[0].click();", leg)
                time.sleep(0.3)
            except Exception:
                driver.execute_script("arguments[0].style.display='block';", fld)
    except Exception:
        pass
    try:
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.XPATH, "//fieldset[@id='fldLembretes']//div[contains(@class,'whiteboard-note')]"))
        )
        return True
    except Exception:
        try:
            WebDriverWait(driver, 1).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(@class,'whiteboard-note')]"))
            )
            return True
        except Exception:
            return False

def expandir_lembretes(driver, timeout=15) -> bool:
    driver.switch_to.default_content()
    _tentar_clicar_aba_lembretes(driver)
    if _expandir_no_contexto(driver):
        return True
    for fr in driver.find_elements(By.TAG_NAME, "iframe"):
        try:
            driver.switch_to.default_content(); driver.switch_to.frame(fr)
            if _expandir_no_contexto(driver):
                return True
        except Exception:
            continue
    driver.switch_to.default_content()
    return False

def _rgb_to_color_name(r:int, g:int, b:int) -> str:
    if abs(r-g)<18 and abs(g-b)<18: return "cinza"
    if r>200 and g<120 and b<120: return "vermelho"
    if r>220 and 120<=g<=200 and b<110: return "laranja"
    if r>220 and g>220 and b<150: return "amarelo"
    if g>200 and r<150 and b<150: return "verde"
    if b>200 or (b>160 and r<140 and g<190): return "azul"
    if max(r,g,b)==r: return "vermelho"
    if max(r,g,b)==g: return "verde"
    return "azul"

def _parse_bgcolor(style_text: str) -> Optional[str]:
    if not style_text: return None
    m = re.search(r"background:\s*rgb\((\d+),\s*(\d+),\s*(\d+)\)", style_text)
    if not m:
        m = re.search(r"background-color:\s*rgb\((\d+),\s*(\d+),\s*(\d+)\)", style_text)
    if not m: return None
    r, g, b = map(int, m.groups())
    return _rgb_to_color_name(r,g,b)

def _coletar_no_contexto(driver, num_proc, cores_desejadas, matcher, aplicar_filtro):
    registros = []
    notes = driver.find_elements(By.XPATH, "//fieldset[@id='fldLembretes']//div[contains(@class,'whiteboard-note')]")
    if not notes:
        notes = driver.find_elements(By.XPATH, "//div[contains(@class,'whiteboard-note')]")
    for note in notes:
        try:
            style = (note.get_attribute("style") or "")
            cor = _parse_bgcolor(style) or "desconhecida"
            if cores_desejadas and cor not in cores_desejadas:
                continue
            def get_txt(xp):
                try: return note.find_element(By.XPATH, xp).text.strip()
                except Exception: return ""
            header = get_txt(".//div[contains(@class,'note-header')]")
            body   = get_txt(".//div[contains(@class,'note-text-wrapper') or contains(@class,'note-content')]")
            if not body:
                body = (note.get_attribute('innerText') or '').strip()
            footer = get_txt(".//div[contains(@class,'note-footer')]")
            texto_integral = "\n".join([t for t in (header, body, footer) if t])
            ok, trecho = (True, None)
            if aplicar_filtro:
                ok, trecho = matcher(texto_integral)
            if ok:
                autor, datahora = "", ""
                m = re.search(r"([a-zA-Z\.\-_]+)\s+(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})", footer)
                if m:
                    autor, datahora = m.group(1), m.group(2)
                registros.append({
                    "processo": num_proc,
                    "link": driver.current_url,
                    "cor": cor,
                    "autor": autor,
                    "data_hora": datahora,
                    "trecho": trecho or "",
                    "conteudo": texto_integral,
                })
        except Exception:
            continue
    return registros

def _ler_texto_generico(driver) -> Optional[str]:
    # 1) textarea
    try:
        vals = []
        for ta in driver.find_elements(By.XPATH, "//textarea"):
            if not ta.is_displayed(): continue
            v = (ta.get_attribute("value") or ta.get_attribute("textContent") or ta.text or "").strip()
            if v: vals.append(v)
        if vals: return max(vals, key=len)
    except Exception: pass
    # 2) contenteditable
    try:
        ceds = driver.find_elements(By.XPATH, "//*[@contenteditable='true']")
        vals = [(el.get_attribute("innerText") or el.text or "").strip() for el in ceds if el.is_displayed()]
        vals = [v for v in vals if v]
        if vals: return max(vals, key=len)
    except Exception: pass
    # 3) editores ricos
    try:
        eds = driver.find_elements(By.XPATH, "//div[contains(@class,'cke_editable') or contains(@class,'jqte_editor') or contains(@class,'ql-editor') or contains(@class,'note-editable')]")
        vals = [(el.get_attribute("innerText") or el.text or "").strip() for el in eds if el.is_displayed()]
        vals = [v for v in vals if v]
        if vals: return max(vals, key=len)
    except Exception: pass
    # 4) iframes do editor
    try:
        for fr in driver.find_elements(By.TAG_NAME, "iframe"):
            try:
                driver.switch_to.frame(fr)
                body_text = driver.execute_script("return (document && document.body && document.body.innerText) || '';")
                driver.switch_to.parent_frame()
                if body_text and body_text.strip():
                    return body_text.strip()
            except Exception:
                driver.switch_to.parent_frame(); continue
    except Exception: pass
    return None

def _coletar_via_edicao(driver, num_proc: str, cores_desejadas, matcher, aplicar_filtro) -> list[dict]:
    registros = []
    botoes = driver.find_elements(
        By.XPATH,
        "//div[contains(@class,'whiteboard') and contains(@class,'note')]//a[.//i[contains(@class,'fa-pencil') or contains(@class,'fa-pen') or contains(@class,'fa-edit')]] | "
        "//div[contains(@class,'whiteboard') and contains(@class,'note')]//a[contains(@title,'Alterar') or contains(translate(@title,'EDITARALTERAR','editaralterar'),'editar') or contains(translate(@title,'ALTERAR','alterar'))] | "
        "//a[contains(@href,'processo_lembrete_destino_alterar') or (contains(@href,'lembrete') and (contains(@href,'editar') or contains(@href,'alterar')))] | "
        "//button[contains(@title,'Editar') or contains(translate(@title,'ALTERAR','alterar'),'alterar') or .//i[contains(@class,'fa-pencil')]]"
    )
    if not botoes:
        return registros

    for btn in botoes:
        try:
            # card p/ cor e rodapé
            try:
                card = btn.find_element(By.XPATH, ".//ancestor::div[contains(@class,'whiteboard') and contains(@class,'note')][1]")
            except Exception:
                try:
                    card = btn.find_element(By.XPATH, ".//ancestor::div[contains(@style,'background')][1]")
                except Exception:
                    card = None
            cor = "desconhecida"; footer_txt = ""
            if card is not None:
                style = (card.get_attribute("style") or "")
                c = _parse_bgcolor(style)
                if c: cor = c
                try:
                    footer_txt = card.find_element(By.XPATH, ".//div[contains(@class,'note-footer')]").text
                except Exception:
                    footer_txt = card.text

            # clique robusto
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
            except Exception: pass
            try:
                WebDriverWait(driver, 6).until(EC.element_to_be_clickable(btn)).click()
            except Exception:
                try: driver.execute_script("arguments[0].click();", btn)
                except Exception:
                    try: ActionChains(driver).move_to_element(btn).pause(0.05).click(btn).perform()
                    except Exception: continue

            time.sleep(0.7)

            # Detecta MODAL visível
            abriu_modal = False
            try:
                modals = driver.find_elements(By.XPATH, "//div[contains(@class,'modal') and contains(@style,'display') and not(contains(@style,'none'))]")
                if modals: abriu_modal = True
            except Exception: pass

            if abriu_modal:
                texto = _ler_texto_generico(driver)
                # fechar modal
                try:
                    driver.switch_to.default_content()
                    for xp in ["//button[normalize-space()='Fechar']", "//a[normalize-space()='Fechar']", "//input[@value='Fechar']", "//div[contains(@class,'modal')]//button[contains(@class,'close')]"]:
                        btns = driver.find_elements(By.XPATH, xp)
                        if btns:
                            driver.execute_script("arguments[0].click();", btns[0]); break
                except Exception: pass
            else:
                # abriu em PÁGINA
                texto = _ler_texto_generico(driver)
                try:
                    driver.back()
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//div[contains(@class,'whiteboard-note')]|//fieldset[@id='fldLembretes']")))
                except Exception:
                    pass

            if not texto:
                continue

            ok, trecho = (True, None)
            if aplicar_filtro:
                ok, trecho = matcher(texto)
            if not ok:
                continue

            autor, datahora = "", ""
            m = re.search(r"([a-zA-Z\.\-_]+)\s+(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})", footer_txt or "")
            if m:
                autor, datahora = m.group(1), m.group(2)

            registros.append({
                "processo": num_proc,
                "link": driver.current_url,
                "cor": cor,
                "autor": autor,
                "data_hora": datahora,
                "trecho": trecho or "",
                "conteudo": texto,
            })
        except Exception:
            continue
    return registros

def coletar_lembretes(driver, wait, num_proc: str,
                      cores_desejadas: Optional[List[str]],
                      matcher: Callable[[str], Tuple[bool, Optional[str]]],
                      aplicar_filtro: bool) -> List[Dict]:
    registros: List[Dict] = []

    expanded = expandir_lembretes(driver, timeout=15)
    if not expanded:
        print("   → Seção Lembretes não visível/expandida (tentaremos mesmo assim).")

    driver.switch_to.default_content()
    regs_doc = _coletar_no_contexto(driver, num_proc, cores_desejadas, matcher, aplicar_filtro)
    registros.extend(regs_doc)

    # iframes do processo
    for fr in driver.find_elements(By.TAG_NAME, "iframe"):
        try:
            driver.switch_to.default_content(); driver.switch_to.frame(fr)
            regs_if = _coletar_no_contexto(driver, num_proc, cores_desejadas, matcher, aplicar_filtro)
            registros.extend(regs_if)
        except Exception:
            continue
    driver.switch_to.default_content()

    # fallback via CANETA (modal ou página)
    if not registros:
        regs_edit = _coletar_via_edicao(driver, num_proc, cores_desejadas, matcher, aplicar_filtro)
        registros.extend(regs_edit)
        if not regs_edit:
            for fr in driver.find_elements(By.TAG_NAME, "iframe"):
                try:
                    driver.switch_to.default_content(); driver.switch_to.frame(fr)
                    regs_if = _coletar_via_edicao(driver, num_proc, cores_desejadas, matcher, aplicar_filtro)
                    registros.extend(regs_if)
                except Exception:
                    continue
            driver.switch_to.default_content()

    print(f"   → Lembretes encontrados (todos os contextos): {len(registros)}")
    return registros
