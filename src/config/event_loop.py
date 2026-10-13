import asyncio
from functools import partial

_app_loop: asyncio.AbstractEventLoop | None = None
_pump = None


def get_app_loop() -> asyncio.AbstractEventLoop:
    global _app_loop
    if _app_loop is None or _app_loop.is_closed():
        _app_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_app_loop)
    return _app_loop


def set_app_loop(loop: asyncio.AbstractEventLoop):
    global _app_loop
    _app_loop = loop


def close_app_loop():
    global _app_loop, _pump
    if _pump is not None:
        _pump.stop()
        _pump = None
    if _app_loop is not None:
        _app_loop.close()
        _app_loop = None


def run_async(coro):
    return get_app_loop().run_until_complete(coro)


def schedule_async(coro, on_success=None, on_error=None):
    """Advance UI coroutines with Qt so awaiting I/O never blocks painting."""
    global _pump
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    loop = get_app_loop()
    if _pump is None:
        _pump = QTimer(QApplication.instance())
        _pump.setInterval(5)

        def tick():
            if loop.is_closed() or loop.is_running():
                return
            loop.call_soon(loop.stop)
            loop.run_forever()

        _pump.timeout.connect(tick)
    if not _pump.isActive():
        _pump.start()
    task = loop.create_task(coro)

    def finished(result):
        if _pump is not None and not asyncio.all_tasks(loop):
            _pump.stop()
        if result.cancelled():
            return
        error = result.exception()
        if error is not None:
            if on_error:
                QTimer.singleShot(0, partial(on_error, error))
            else:
                import logging

                logging.getLogger(__name__).error("UI operation failed", exc_info=error)
        elif on_success:
            value = result.result()
            QTimer.singleShot(0, partial(on_success, value))

    task.add_done_callback(finished)
    return task
