import asyncio

_app_loop: asyncio.AbstractEventLoop = None


def get_app_loop() -> asyncio.AbstractEventLoop:
    global _app_loop
    if _app_loop is None:
        _app_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_app_loop)
    return _app_loop


def set_app_loop(loop: asyncio.AbstractEventLoop):
    global _app_loop
    _app_loop = loop


def close_app_loop():
    global _app_loop
    if _app_loop is not None:
        _app_loop.close()
        _app_loop = None


def run_async(coro):
    return get_app_loop().run_until_complete(coro)
