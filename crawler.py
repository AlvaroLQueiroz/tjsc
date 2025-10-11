import asyncio
import logging
from playwright.async_api import async_playwright

from src.crawler.locator import get_my_locators
from src.constants import DOMAIN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def testing():
    async with async_playwright() as playwright:
        browser = await playwright.webkit.launch(headless=False, slow_mo=800)
        context = await browser.new_context(
            base_url=DOMAIN, storage_state="data/state.json"
        )
        page = await context.new_page()
        await page.goto("/")
        logger.info("Starting crawler...")
        await get_my_locators(page, bool)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(testing())
