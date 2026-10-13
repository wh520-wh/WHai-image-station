"""Capture the actual QML UI with an isolated database; no provider requests."""

import argparse
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QUrl
from PySide6.QtGui import QFontDatabase
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.config import constants
from src.config.database import Database
from src.config.event_loop import close_app_loop, get_app_loop
from src.desktop import StudioBridge


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    for name in ("msyh.ttc", "segoeui.ttf"):
        font = Path("C:/Windows/Fonts") / name
        if font.exists():
            QFontDatabase.addApplicationFont(str(font))
    with tempfile.TemporaryDirectory(prefix="whai-preview-") as temporary:
        constants.GENERATIONS_DIR = str(Path(temporary) / "images")
        constants.THUMBNAILS_DIR = str(Path(temporary) / "thumbs")
        db = Database(str(Path(temporary) / "preview.db"))
        loop = get_app_loop()
        loop.run_until_complete(db.connect())
        bridge = StudioBridge()
        engine = QQmlApplicationEngine()
        warnings = []
        engine.warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
        engine.rootContext().setContextProperty("studio", bridge)
        engine.load(QUrl.fromLocalFile(str(Path(__file__).parents[1] / "src/ui/Main.qml")))
        if not engine.rootObjects():
            bridge._timer.stop()
            loop.run_until_complete(db.close())
            raise RuntimeError("QML failed to load: " + "\n".join(warnings))
        window = engine.rootObjects()[0]
        assert isinstance(window, QQuickWindow)
        QTest.qWait(250)
        window.grabWindow().save(str(output / "splash.png"))
        loop.run_until_complete(bridge.initialize(db))
        for page in ("create", "gallery", "prompts", "sources", "tools", "settings"):
            window.setProperty("currentPage", page)
            QTest.qWait(250)
            window.grabWindow().save(str(output / f"{page}.png"))
        window.setProperty("currentPage", "create")
        bridge.update(dark=True)
        QTest.qWait(200)
        window.grabWindow().save(str(output / "dark.png"))
        window.setWidth(1000)
        window.setHeight(680)
        bridge.update(dark=False)
        QTest.qWait(200)
        window.grabWindow().save(str(output / "compact.png"))
        window.close()
        bridge._timer.stop()
        loop.run_until_complete(db.close())
        del engine
        app.processEvents()
    close_app_loop()
    print(f"Captured 9 views in {output}")


if __name__ == "__main__":
    main()
