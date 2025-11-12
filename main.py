import asyncio
from datetime import datetime
import logging
import sys

from async_tkinter_loop import async_mainloop

from src.constants import LOG_PATH
from src.interface.app import start_application
from src.interface.root import rootWindow

from os import environ
from pathlib import Path
from sys import base_prefix
import platform

if not ("TCL_LIBRARY" in environ and "TK_LIBRARY" in environ):
    tk_dir = "tcl" if platform.system() == "Windows" else "lib"
    tk_path = Path(base_prefix) / tk_dir
    print(tk_path)
    environ["TCL_LIBRARY"] = str(next(tk_path.glob("tcl8.*")))
    environ["TK_LIBRARY"] = str(next(tk_path.glob("tk8.*")))


LOG_FORMAT = "%(asctime)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s"
# Get the root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)  # Set the desired minimum logging level

# Create a console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)  # Console will only show DEBUG and above
console_formatter = logging.Formatter(LOG_FORMAT)
console_handler.setFormatter(console_formatter)
root_logger.addHandler(console_handler)

# Create a file handler
file_handler = logging.FileHandler(
    LOG_PATH / f"app_{datetime.now().strftime('%Y-%m-%d')}.log"
)
file_handler.setLevel(logging.DEBUG)  # File will capture all DEBUG and above
file_formatter = logging.Formatter(LOG_FORMAT)
file_handler.setFormatter(file_formatter)
root_logger.addHandler(file_handler)

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # This is necessary to wait the async loop to start
    rootWindow.after(20, start_application)

    async_mainloop(rootWindow, event_loop=loop)
