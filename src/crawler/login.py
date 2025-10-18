import logging
import json
from typing import Callable

from playwright.async_api import BrowserContext, Page, TimeoutError

from src.constants import EPROC_CONTROLADOR, EPROC_PROFILE, EPROC_PROFILE_SELECTOR, SECRET_PATH, STATE_PATH, EPROC_HOME

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


async def select_profile(page: Page) -> None:
    try:
        await page.wait_for_load_state()
        if await page.get_by_role("heading", name="Seleção de perfil").count():
            logger.info("Selecting profile...")
            await page.get_by_role("button", name=EPROC_PROFILE).click()
    except TimeoutError as e:
        logger.warning("Error selecting profile: %s", e)


async def fill_login_form(username: str, password: str, page: Page) -> None:
    try:
        logger.info("Filling login form...")
        await page.get_by_role("textbox", name="Usuário").fill(username)
        await page.get_by_role("textbox", name="Senha").fill(password)
        await page.get_by_role("button", name="Entrar").click()

        if await page.locator("id=input-error").count():
            raise ValueError("Invalid username or password")
    except TimeoutError as e:
        logger.error("Login form not found: %s", e)
        raise
    except ValueError as e:
        logger.error("Invalid username or password: %s", e)
        raise


async def is_logged_in(page: Page, set_user_status: Callable[[dict], None]) -> None:
    logger.info("Checking login status...")
    try:
        await page.goto(EPROC_HOME)
    except TimeoutError as e:
        pass

    try:
        await page.wait_for_load_state()
        if await page.get_by_role("textbox", name="Usuário").count():
            logger.info("Not logged in, trying login...")
            username, password = get_auth_data()
            await fill_login_form(username, password, page)

        await select_profile(page)

        await page.wait_for_url(f"**{EPROC_CONTROLADOR}**")
    except (TimeoutError, ValueError) as e:
        logger.warning("User not logged in: %s", e)
        set_user_status({ "logged_in": False })
        return
    logger.info("User is logged in")
    set_user_status({ "logged_in": True })


async def make_login(username: str, password: str, otp_code: str, page: Page, context: BrowserContext, set_user_status: Callable[[dict], None]) -> None:
    logger.info("Logging in...")

    try:
        await page.goto(EPROC_HOME)
    except TimeoutError:
        pass

    try:
        await fill_login_form(username, password, page)
    except TimeoutError:
        set_user_status({ "logged_in": False, "message": "Erro ao carregar o formulário de login" })
        return
    except ValueError:
        logger.error("Login failed")
        set_user_status({ "logged_in": False, "message": "Usuário ou senha inválidos" })
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
    except TimeoutError as e:
        logger.error("OTP form not found: %s", e)
        set_user_status({ "logged_in": False, "message": "Erro ao carregar o formulário 2FA" })
        return
    except ValueError as e:
        logger.error("Invalid OTP code: %s", e)
        set_user_status({ "logged_in": False, "message": "Código 2FA inválido" })
        return

    await context.storage_state(path=STATE_PATH)

    await select_profile(page)

    try:
        await page.wait_for_url(f"**{EPROC_CONTROLADOR}**")
    except TimeoutError as e:
        logger.error("Login failed: %s", e)
        set_user_status({ "logged_in": False, "message": "Erro ao carregar a página inicial" })
        return

    logger.info("Logged in")
    await context.storage_state(path=STATE_PATH)
    logger.info("Storage state saved")
    set_user_status({ "logged_in": True })
