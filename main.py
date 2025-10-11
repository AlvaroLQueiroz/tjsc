import asyncio

from src.interface.app import app
from async_tkinter_loop import async_mainloop


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    async_mainloop(app, event_loop=loop)
