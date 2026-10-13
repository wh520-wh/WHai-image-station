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
    tool_stage = 0
    timer = QTimer()
    timer.setInterval(120)

    def tick():
        nonlocal page_index, tool_stage
        assert app._bridge
        state = app._bridge.property("state")
        if time.perf_counter() - started > 20:
            timer.stop()
            report["error"] = "Startup or local tool check timed out"
            app.quit()
            return
        if state["ready"]:
            if not report["ready"]:
                report["ready"] = True
                report["ready_seconds"] = round(time.perf_counter() - started, 3)
            if page_index < len(pages):
                window.setProperty("currentPage", pages[page_index])
                report["pages"].append(pages[page_index])
                page_index += 1
                return
            if tool_stage == 0:
                from PIL import Image

                source = target / "offline-tool.png"
                Image.new("RGBA", (160, 120), (40, 93, 69, 120)).save(source)
                window.setProperty("currentPage", "tools")
                app._bridge.loadToolImage(str(source))
                tool_stage = 1
                return
            if state["toolLoading"] or state["toolBusy"]:
                return
            if tool_stage == 1:
                if not state["toolInput"]:
                    report["error"] = state["toolError"] or "Local image input failed"
                else:
                    app._bridge.runImageTool("resize", "WebP", 80, 85)
                    tool_stage = 2
                    return
            else:
                result = state["toolResult"]
                report["tools_checked"] = (
                    result.get("width") == 80
                    and result.get("height") == 60
                    and result.get("format") == "WEBP"
                    and result.get("recordSaved") is True
                    and not state["toolError"]
                )
            timer.stop()
            app.quit()

    timer.timeout.connect(tick)
    timer.start()
    app.exec()
    (target / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report["ready"] and report["icon_loaded"] and report.get("tools_checked") and not report["warnings"] else 1
