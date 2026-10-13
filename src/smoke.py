"""Offline startup check shared by source and packaged application validation."""

import json
import time
from pathlib import Path

from PySide6.QtCore import QTimer

from src.config import constants


def run_smoke(directory):
    from src.app import ImageMakerApp

    target = Path(directory).resolve()
    target.mkdir(parents=True, exist_ok=True)
    constants.DEFAULT_DB_PATH = str(target / "smoke.db")
    constants.GENERATIONS_DIR = str(target / "images")
    constants.THUMBNAILS_DIR = str(target / "thumbs")
    started = time.perf_counter()
    report = {"ready": False, "pages": [], "warnings": []}
    app = ImageMakerApp(["WHai", "--smoke-test"])
    report["icon_loaded"] = not app.windowIcon().isNull()
    assert app._engine and app._bridge
    app._engine.warnings.connect(lambda errors: report["warnings"].extend(e.toString() for e in errors))
    window = app._engine.rootObjects()[0]
    pages = ["create", "gallery", "prompts", "sources", "tools", "settings"]
    page_index = 0
    timer = QTimer()
    timer.setInterval(120)

    def tick():
        nonlocal page_index
        assert app._bridge
        if app._bridge._state["ready"]:
            if not report["ready"]:
                report["ready"] = True
                report["ready_seconds"] = round(time.perf_counter() - started, 3)
            if page_index < len(pages):
                window.setProperty("currentPage", pages[page_index])
                report["pages"].append(pages[page_index])
                page_index += 1
                return
            timer.stop()
            app.quit()
        elif time.perf_counter() - started > 15:
            timer.stop()
            report["error"] = "Startup timed out"
            app.quit()

    timer.timeout.connect(tick)
    timer.start()
    app.exec()
    (target / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report["ready"] and report["icon_loaded"] and not report["warnings"] else 1
