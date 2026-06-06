# tests/test_cross_platform_paths.py
"""Verify that file manager open operations are cross-platform."""
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_open_folder_uses_qdesktop_services(qapp):
    """Verify cross-platform file manager open logic uses QDesktopServices, not os.startfile."""
    from src.widgets.history_panel import HistoryPanel
    with patch("src.widgets.history_panel.QDesktopServices.openUrl") as mock_open:
        panel = HistoryPanel.__new__(HistoryPanel)  # 不调用 __init__
        path = "/some/image.png"
        panel._open_in_file_manager(path)
        mock_open.assert_called_once()
        called_url = mock_open.call_args[0][0]
        assert "image" in called_url.toString() or called_url.isLocalFile()
