import logging
from typing import Callable

from playwright.async_api import BrowserContext, Page, TimeoutError


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def get_processes(page: Page, locator: str, set_processes: Callable[[dict], None]) -> None:
    await page.get_by_role("link", name="localizadores").click()
    await page.get_by_role("link", name="Meus localizadores").click()
    processes = {}

    has_next_page = True
    while has_next_page:
        for process_line in await page.locator("#tabelaLocalizadores tbody tr").all():
            process_number_col =  process_line.locator("td").nth(1).locator("a").nth(0)
            text = await process_number_col.inner_text()
            link = await process_number_col.get_attribute("href")
            processes[text] = link
        try:
            await page.get_by_role("button", name="Próxima Página").click()
        except TimeoutError:
            has_next_page = False

    set_processes(processes)


async def download_process_files(page: Page, process: dict[str, str], file_names: list[str]) -> None:
    await page.goto(process["link"])

    for file_anchor in await page.locator(".infraLinkDocumento").all():
        file_name = await file_anchor.inner_text()
        if file_name not in file_names:
            continue
        file_link = await file_anchor.get_attribute("href")
        data = {
            "name": file_name,
            "link": file_link
        }

    set_data(data)
