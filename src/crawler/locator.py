import logging
from typing import Callable

from playwright.async_api import BrowserContext, Page, TimeoutError

from src.crawler.login import EPROC_HOME


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def go_to_locators_page(page: Page) -> None:
    try:
        await page.goto(EPROC_HOME)
        await page.get_by_role("link", name="localizadores").click()
        await page.get_by_role("link", name="Meus localizadores").click()
    except TimeoutError:
        logger.error("Could not navigate to locators page")
        return


async def get_my_locators(page: Page, set_locator: Callable[[dict], None]) -> None:
    await go_to_locators_page(page)
    locators = {}
    for locator in await page.locator(".infraTable .infraTrClara").all():
        text = await locator.inner_text()
        link = await locator.locator("a").get_attribute("href")
        locators[text] = link
    set_locator(locators)
