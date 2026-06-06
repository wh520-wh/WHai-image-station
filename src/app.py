import sys
import os
import asyncio

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer, QSharedMemory

from src.widgets.main_window import MainWindow
from src.widgets.theme import APP_STYLESHEET, app_font
from src.config import constants, database, encryption
from src.config.event_loop import get_app_loop, set_app_loop, close_app_loop, run_async
from src.adapters import init_adapters
from src.managers import QueueManager, PromptManager, HistoryManager


class ImageMakerApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName(constants.APP_NAME)
        self.setApplicationVersion(constants.APP_VERSION)
        self.setFont(app_font())
        self.setStyleSheet(APP_STYLESHEET)

        self._db: database.Database = None
        self._main_window: MainWindow = None
        self._cleaned_up = False

        # 异步初始化
        QTimer.singleShot(0, self._init_async)

    async def _async_init(self):
        os.makedirs(constants.GENERATIONS_DIR, exist_ok=True)
        os.makedirs(constants.THUMBNAILS_DIR, exist_ok=True)
        # 初始化数据库
        self._db = database.Database.get_instance()
        await self._db.connect()

        # 初始化适配器
        init_adapters()

        # 初始化管理器
        queue_mgr = QueueManager.get_instance()
        await queue_mgr.initialize(self._db)

        prompt_mgr = PromptManager.get_instance()
        await prompt_mgr.initialize(self._db)

        history_mgr = HistoryManager.get_instance()
        await history_mgr.initialize(self._db)

        # 启动队列
        await queue_mgr.start()

    def _init_async(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        set_app_loop(loop)
        loop.run_until_complete(self._async_init())

        self.aboutToQuit.connect(self._on_about_to_quit)

        self._main_window = MainWindow(self._db)
        self._main_window.show()

    def quit(self):
        self._do_cleanup()
        super().quit()

    def _on_about_to_quit(self):
        self._do_cleanup()

    def _do_cleanup(self):
        if self._cleaned_up:
            return
        self._cleaned_up = True
        from src.config.event_loop import get_app_loop
        loop = get_app_loop()
        if loop is None or loop.is_closed():
            return
        loop.run_until_complete(self._cleanup())

    async def _cleanup(self):
        queue_mgr = QueueManager.get_instance()
        await queue_mgr.stop()
        if self._db:
            await self._db.close()


_SHARED_MEM_KEY = "imageMaker_SingleInstance_9E4F7B2A"


def main():
    shared_mem = QSharedMemory(_SHARED_MEM_KEY)
    # 尝试创建共享内存锁；失败时先清理残留再重试一次
    if not shared_mem.create(1):
        if shared_mem.attach():
            shared_mem.detach()
        # 重试
        if not shared_mem.create(1):
            temp_app = QApplication(sys.argv)
            QMessageBox.warning(
                None,
                constants.APP_NAME,
                "imageMaker 已在运行中，请勿重复启动。",
            )
            return 1
    app = ImageMakerApp(sys.argv)
    app.aboutToQuit.connect(lambda: shared_mem.detach() if shared_mem.isAttached() else None)
    ret = app.exec()
    if shared_mem.isAttached():
        shared_mem.detach()
    return ret

