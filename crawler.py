import logging
from playwright.sync_api import sync_playwright

from src.crawler.login import login
from src.constants import DOMAIN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def testing():
    with sync_playwright() as playwright:
        browser = playwright.webkit.launch(headless=False, slow_mo=800)
        context = browser.new_context(
            base_url=DOMAIN, storage_state="data/state.json"
        )
        page = context.new_page()
        logger.info("Starting crawler...")
        login(page, context)

        browser.close()


if __name__ == "__main__":
    testing()
