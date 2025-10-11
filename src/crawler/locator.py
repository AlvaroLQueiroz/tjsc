import logging
from typing import Callable

from playwright.async_api import BrowserContext, Page, TimeoutError


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def get_my_locators(page: Page, set_locator_list: Callable[[str], None]) -> None:
    await page.get_by_role("link", name="localizadores").click()
    await page.get_by_role("link", name="Meus localizadores").click()
    locators = []
    for locator in await page.locator(".infraTable .infraTrClara").all():
        text = await locator.inner_text()
        link = await locator.locator("a").get_attribute("href")
        locators.append(f"{text}||{link}")
    set_locator_list("|||".join(locators))


async def make_login(username: str, password: str, otp_code: str, page: Page, context: BrowserContext, set_user_status: Callable[[bool], None]) -> None:
    logger.info("Logging in...")

    try:
        await page.goto("/")
        await page.wait_for_url("**/realms/eproc/protocol/openid-connect/auth**")
    except TimeoutError:
        logger.error("Login page not loaded")
        set_user_status(False)
        return

    await page.locator("id=username").fill(username)
    await page.locator("id=password").fill(password)
    await page.get_by_role("button", name="Entrar").click()

    try:
        if await page.locator("id=input-error").count() > 0:
            logger.error("Invalid username or password")
            set_user_status(False)
            return
    except TimeoutError:
        pass

    await page.locator("id=saveDevice").check()

    await page.locator("id=otp").fill(otp_code)
    await page.get_by_role("button", name="Entrar").click()

    if await page.locator("id=input-error-otp-code").count():
        logger.error("Invalid OTP code")
        set_user_status(False)
        return

    logger.info("Logged in")
    await context.storage_state(path="data/state.json")
    logger.info("Storage state saved")
    set_user_status(True)
