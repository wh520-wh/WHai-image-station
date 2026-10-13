import asyncio
import os
import sys
from pathlib import Path

from PySide6.QtCore import QSharedMemory, QTimer, QUrl
from PySide6.QtGui import QIcon, QWindow
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication, QMessageBox
from shiboken6 import delete

from src.adapters import init_adapters
from src.config import constants, database
from src.config.event_loop import close_app_loop, get_app_loop, schedule_async, set_app_loop
from src.desktop import StudioBridge
from src.managers import HistoryManager, PromptManager, QueueManager
from src.widgets.main_window import MainWindow
from src.widgets.theme import APP_STYLESHEET, app_font


class ImageMakerApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName(constants.APP_NAME)
        self.setApplicationVersion(constants.APP_VERSION)
        self.setWindowIcon(QIcon(str(Path(__file__).parent / "ui" / "assets" / "app.ico")))
        self.setFont(app_font())
        self.setStyleSheet(APP_STYLESHEET)

        self._db: database.Database | None = None
        self._main_window: MainWindow | None = None
        self._cleaned_up = False
        self._bridge: StudioBridge | None = None
        self._engine: QQmlApplicationEngine | None = None
        if "--widgets" not in argv:
            QQuickStyle.setStyle("Basic")
            self._bridge = StudioBridge(self)
            self._engine = QQmlApplicationEngine(self)
            self._engine.rootContext().setContextProperty("studio", self._bridge)
            self._engine.load(QUrl.fromLocalFile(str(Path(__file__).parent / "ui" / "Main.qml")))
            if not self._engine.rootObjects():
                raise RuntimeError("Qt Quick 界面加载失败，请检查安装中的 QML 文件。")
        self.aboutToQuit.connect(self._on_about_to_quit)

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
        if self._bridge:
            await self._bridge.initialize(self._db)

    def _init_async(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        set_app_loop(loop)
        schedule_async(self._async_init(), on_success=lambda _: self._show_window(), on_error=self._show_init_error)

    def _show_window(self):

        if not self._bridge:
            self._main_window = MainWindow(self._db)
            self._main_window.show()

    def _show_init_error(self, error):
        if "--smoke-test" in self.arguments():
            self.quit()
            return
        QMessageBox.critical(None, constants.APP_NAME, f"启动失败：{error}")
        self.quit()

    def quit(self):
        self._do_cleanup()
        super().quit()

    def _on_about_to_quit(self):
        self._do_cleanup()

    def _do_cleanup(self):
        if self._cleaned_up:
            return
        self._cleaned_up = True
        loop = get_app_loop()
        if loop is None or loop.is_closed():
            return
        loop.run_until_complete(self._cleanup())
        close_app_loop()
        # Destroy Quick windows/engine while QApplication and its scene graph are alive.
        if self._engine:
            for root in self._engine.rootObjects():
                if isinstance(root, QWindow):
                    root.close()
            delete(self._engine)
            self._engine = None

    async def _cleanup(self):
        current = asyncio.current_task()
        pending = [task for task in asyncio.all_tasks() if task is not current]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        if self._bridge:
            await self._bridge.shutdown()
        queue_mgr = QueueManager.get_instance()
        await queue_mgr.stop()
        if self._db:
            await self._db.close()


_SHARED_MEM_KEY = "imageMaker_SingleInstance_9E4F7B2A"


def main():
    smoke_arg = next((arg for arg in sys.argv if arg.startswith("--smoke-test=")), None)
    if smoke_arg:
        from src.smoke import run_smoke

        return run_smoke(smoke_arg.split("=", 1)[1])
    shared_mem = QSharedMemory(_SHARED_MEM_KEY)
    # 尝试创建共享内存锁；失败时先清理残留再重试一次
    if not shared_mem.create(1):
        if shared_mem.attach():
            shared_mem.detach()
        # 重试
        if not shared_mem.create(1):
            app = QApplication(sys.argv)
            QMessageBox.warning(
                None,
                constants.APP_NAME,
                "WHai Image Station 已在运行中，请勿重复启动。",
            )
            return 1
    app = ImageMakerApp(sys.argv)
    app.aboutToQuit.connect(lambda: shared_mem.detach() if shared_mem.isAttached() else None)
    ret = app.exec()
    if shared_mem.isAttached():
        shared_mem.detach()
    return ret
