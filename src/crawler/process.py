import logging
import re
from typing import Callable

from playwright.async_api import BrowserContext, Page, TimeoutError

from src.constants import DOWNLOADED_PATH, EPROC
from src.interface.loading import LoadingFrame


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROCESS_COUNTER_RE = re.compile(r"Lista de Processos por Localizador \((\d+) registros.*")

async def get_processes(page: Page, locator: str, loading_frame: LoadingFrame, set_processes: Callable[[dict], None]) -> None:
    logger.info("Getting processes...")
    await page.get_by_role("button", name="Meus localizadores").click()
    await page.wait_for_load_state()
    await page.get_by_role("link", name=locator).click()
    await page.wait_for_load_state()
    processes = {}

    table = page.get_by_role("table", name="Lista de Processos por Localizador")
    num_processes = PROCESS_COUNTER_RE.match(await table.locator("caption").inner_text())
    num_processes = int(num_processes.group(1)) if num_processes else 0
    logger.info(f"Found {num_processes} processes.")
    loading_frame.set_maximum(num_processes)

    has_next_page = True
    while has_next_page:
        rows = await table.locator("tr:is(.infraTrClara,.infraTrEscura)").all()
        for process in rows:
            loading_frame.update_progress()
            process_number_col = process.locator("td").nth(1).locator("a").nth(0)
            text = await process_number_col.inner_text()
            link = await process_number_col.get_attribute("href")
            processes[text] = link
        try:
            await page.get_by_role("link", name="Próxima Página").nth(0).click()
            await page.wait_for_load_state()
        except TimeoutError:
            has_next_page = False

    logger.info(f"Total processes collected: {len(processes)}")
    set_processes(processes)


async def download_process_files(context: BrowserContext, page: Page, process: dict[str, str], file_name_pattern: re.Pattern, key_words: str, loading_frame: LoadingFrame) -> None:
    for process_number, link in process.items():
        loading_frame.update_progress()
        await page.goto(f"{EPROC}{link}")

        path = DOWNLOADED_PATH / process_number.replace("/", "_")
        path.mkdir(parents=True, exist_ok=True)

        files = await page.locator(".infraLinkDocumento").all()
        logger.info(f"Found {len(files)} files for process {process_number}...")
        for file_anchor in files:
            file_name = await file_anchor.inner_text()
            new_page = context.wait_for_event("page")
            await file_anchor.click()
            new_page = await new_page
            await new_page.wait_for_load_state()
            await new_page.get_by_role("button", name="Download").click()
            await new_page.get_by_role("button", name="Download").click()
            doc_content = await new_page.locator("body").inner_text()
            print("Nome do Arquivo: ", bool(file_name_pattern.match(file_name)))
            print("Contem Palavra: ", key_words in doc_content)
            print("Conteudo: ", len(doc_content))
            await new_page.screenshot(
                path=path / f"{file_name}.png",
                full_page=True,
                type="png",
                omit_background=True
                )
            await new_page.close()
            # if file_name_pattern.match(file_name):

                # if not file_name_pattern.match(file_name):
                #     continue
                # print(file_name)
                # file_link = await file_anchor.get_attribute("href")
                # data = {
                #     "name": file_name,
                #     "link": file_link
                # }
