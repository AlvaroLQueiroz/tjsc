import logging
from typing import Callable

from playwright.async_api import BrowserContext, Page, TimeoutError

from src.constants import DOMAIN
from src.types import Status

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def is_logged_in(page: Page, set_user_status: Callable[[bool], None]) -> None:
    try:
        await page.goto("/")
        await page.wait_for_url("**/app/home**", timeout=5000)
        set_user_status(True)
    except TimeoutError:
        set_user_status(False)


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
