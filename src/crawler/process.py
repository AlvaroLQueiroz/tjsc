import logging
import re
from typing import Any, Callable
from urllib.parse import urlparse, parse_qs

from playwright.async_api import Page, TimeoutError

from src.constants import DOMAIN, DOWNLOADED_PATH, EPROC
from src.interface.loading import LoadingFrame


logger = logging.getLogger(__name__)

PROCESS_COUNTER_RE = re.compile(
    r"Lista de Processos por Localizador \((\d+) registros.*"
)


async def get_processes(
    page: Page,
    locator: str,
    loading_frame: LoadingFrame,
    set_processes: Callable[[dict], None],
) -> None:
    logger.debug("Getting processes...")
    logger.debug("Going to Meus localizadores page.")
    await page.get_by_role("button", name="Meus localizadores").click()
    await page.wait_for_load_state()
    logger.debug("Clicking on locator: %s", locator)
    await page.get_by_role("link", name=locator).click()
    await page.wait_for_load_state()
    processes = {}

    logger.debug("Collecting processes from the table.")
    table = page.get_by_role("table", name="Lista de Processos por Localizador")
    num_processes = PROCESS_COUNTER_RE.match(
        await table.locator("caption").inner_text()
    )
    num_processes = int(num_processes.group(1)) if num_processes else 0
    logger.info("Found %s processes", num_processes)
    loading_frame.set_maximum(num_processes)

    has_next_page = True
    while has_next_page:
        rows = await table.locator("tr:is(.infraTrClara,.infraTrEscura)").all()
        for index, process in enumerate(rows):
            logger.debug("Collecting process %s", index)
            loading_frame.update_progress()
            process_number_col = process.locator("td").nth(1).locator("a").nth(0)
            text = await process_number_col.inner_text()
            link = await process_number_col.get_attribute("href")
            processes[text] = {"link": link}
        try:
            await page.get_by_role("link", name="Próxima Página").nth(0).click()
            await page.wait_for_load_state()
            logger.debug("Navigated to next page of processes.")
        except TimeoutError:
            has_next_page = False

    logger.info("Total processes collected: %s", len(processes))
    set_processes(processes)


def flatten_dict(d: dict[str, list[str]]) -> dict[str, str]:
    return {k: v[0] for k, v in d.items()}


async def download_process_files(
    page: Page,
    processes: dict[str, dict[str, Any]],
    file_name_pattern: re.Pattern,
    set_processes: Callable[[dict[str, dict[str, Any]]], None],
    loading_frame: LoadingFrame,
) -> None:
    logger.debug("Downloading process files...")
    for process_number, process in processes.items():
        logger.debug("Downloading files for process: %s", process_number)
        if "files" not in process:
            processes[process_number]["files"] = []
        loading_frame.update_progress()
        await page.goto(f"{EPROC}{process['link']}")

        process_folder = DOWNLOADED_PATH / process_number.replace("/", "_")
        process_folder.mkdir(parents=True, exist_ok=True)
        downloaded_files_counter = 0

        files_anchors = await page.locator(".infraLinkDocumento").all()
        logger.info(f"Found {len(files_anchors)} files for process {process_number}...")
        for file_index, file_anchor in enumerate(files_anchors, 1):
            file_link = await file_anchor.get_attribute("href")
            file_name = await file_anchor.inner_text() + f"_{file_index}"
            if not file_name_pattern.match(file_name):
                logger.debug("Skipping file %s as it does not match the pattern.", file_name)
                continue
            logger.debug("Downloading file %s from %s", file_name, file_link)
            parsed_url = urlparse(file_link or "")
            url_params = flatten_dict(parse_qs(parsed_url.query))
            url_params["acao"] = "acessar_documento_implementacao"
            url_params["acao_origem"] = "acessar_documento"
            url_params["nome_documento"] = file_name

            file_path = process_folder / file_name
            file_path = file_path.with_suffix(".pdf")
            response = await page.request.get(
                f"{DOMAIN}{EPROC}{parsed_url.path}", params=url_params
            )

            if response.status != 200:
                logger.error("Failed to download file: %s -- %s", file_path, await response.body())
                continue
            with open(file_path, "wb") as f:
                f.write(await response.body())
            downloaded_files_counter += 1
            logger.debug("Downloaded file %s to %s", file_name, file_path)
            processes[process_number]["files"].append(str(file_path))
        logger.info(
            f"Downloaded {downloaded_files_counter} files for process {process_number}."
        )
    set_processes(processes)
