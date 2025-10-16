import logging
import json
from typing import Callable

from playwright.async_api import BrowserContext, Page, TimeoutError

from src.constants import EPROC_CONTROLADOR, EPROC_PROFILE, SECRET_PATH, STATE_PATH, EPROC_HOME

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_auth_data() -> tuple[str, str]:
    with open(SECRET_PATH) as f:
        secrets = json.load(f)
    username = secrets.get("username")
    password = secrets.get("password")
    if not username or not password:
        logger.error("Username or password environment variables not set")
        return ("", "")
    return username, password


async def fill_login_form(username: str, password: str, page: Page) -> bool:
    try:
        logger.info("Filling login form...")
        await page.get_by_role("textbox", name="Usuário").fill(username)
        await page.get_by_role("textbox", name="Senha").fill(password)
        await page.get_by_role("button", name="Entrar").click()

        if await page.locator("id=input-error").count():
            raise ValueError("Invalid username or password")
    except TimeoutError:
        logger.error("Login form not found")
        return False
    except ValueError:
        logger.error("Invalid username or password")
        return False
    return True


async def is_logged_in(page: Page, set_user_logged_in: Callable[[bool], None]) -> None:
    logger.info("Checking login status...")
    logged_in = False
    try:
        await page.goto(EPROC_HOME)

        if await page.get_by_role("textbox", name="Usuário").count():
            logger.info("Not logged in, performing login...")
            username, password = get_auth_data()
            logged_in = await fill_login_form(username, password, page)
        await page.wait_for_url(f"**{EPROC_CONTROLADOR}**")
    except TimeoutError:
        set_user_logged_in(False)
        return

    set_user_logged_in(logged_in)


async def make_login(username: str, password: str, otp_code: str, page: Page, context: BrowserContext, set_user_logged_in: Callable[[bool], None]) -> None:
    logger.info("Logging in...")

    try:
        await page.goto(EPROC_HOME)
    except TimeoutError:
        logger.error("Login page not loaded")
        set_user_logged_in(False)
        return

    logged_in = await fill_login_form(username, password, page)
    if not logged_in:
        set_user_logged_in(False)
        return

    try:
        await page.get_by_role("alert", name="Verify you are human").click()
    except TimeoutError:
        logger.info("No captcha found, proceeding...")

    try:
        logger.info("Filling OTP form...")
        await page.locator("id=saveDevice").check()
        await page.locator("id=otp").fill(otp_code)
        await page.get_by_role("button", name="Entrar").click()

        if await page.locator("id=input-error-otp-code").count():
            raise ValueError("Invalid OTP code")
    except TimeoutError:
        logger.error("OTP form not found")
        set_user_logged_in(False)
        return
    except ValueError:
        logger.error("Invalid OTP code")
        set_user_logged_in(False)
        return

    await context.storage_state(path=STATE_PATH)

    try:
        logger.info("Selecting profile...")
        await page.wait_for_url(f"**{EPROC_HOME}**")
        await page.get_by_role("button", name=EPROC_PROFILE).click()
    except TimeoutError:
        logger.warning("Skipped profile selection")

    try:
        await page.wait_for_url(f"**{EPROC_CONTROLADOR}**")
    except TimeoutError:
        logger.error("Login failed")
        set_user_logged_in(False)
        return

    logger.info("Logged in")
    await context.storage_state(path=STATE_PATH)
    logger.info("Storage state saved")
    set_user_logged_in(True)
