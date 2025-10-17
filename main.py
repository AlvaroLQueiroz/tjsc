import asyncio

from async_tkinter_loop import async_mainloop

from src.interface.app import start_application
from src.interface.root import rootWindow

if __name__ == "__main__":

    # This is necessary to wait the async loop to start
    rootWindow.after(20, start_application)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    async_mainloop(rootWindow, event_loop=loop)
