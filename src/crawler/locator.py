import logging
from typing import Callable

from playwright.async_api import BrowserContext, Page, TimeoutError

from src.crawler.login import EPROC_HOME


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def get_my_locators(page: Page, set_locator: Callable[[dict], None]) -> None:
    await page.get_by_role("button", name="Meus localizadores").click()
    await page.wait_for_load_state()
    locators = {}
    for locator in await page.locator(".infraTable .infraTrClara").all():
        anchor = locator.locator("a")
        text = await anchor.get_attribute("aria-label")
        link = await anchor.get_attribute("href")
        locators[text] = link
    set_locator(locators)
