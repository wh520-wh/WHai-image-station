# src/widgets/batch_ops_bar.py
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Signal
from src.widgets.theme import COLORS, button_style


class BatchOpsBar(QFrame):
    delete_requested = Signal(list)
    move_requested = Signal(list)
    export_requested = Signal(list)
    tag_requested = Signal(list)
    clear_selection_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_ids = []
        self._setup_ui()

    def _setup_ui(self):
        self.setProperty("imageMakerBatchOpsBar", True)
        self.setStyleSheet(f"""
            QFrame[imageMakerBatchOpsBar="true"] {{
                background: {COLORS['panel']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)

        self.count_label = QLabel("已选择 0 项")
        self.count_label.setStyleSheet(f"color: {COLORS['text']}; font-size: 13px;")
        layout.addWidget(self.count_label)

        layout.addStretch()

        self.delete_btn = QPushButton("删除")
        self.delete_btn.setStyleSheet(button_style("danger_ghost"))
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(list(self._selected_ids)))

        self.move_btn = QPushButton("移动到...")
        self.move_btn.setStyleSheet(button_style("secondary"))
        self.move_btn.clicked.connect(lambda: self.move_requested.emit(list(self._selected_ids)))

        self.export_btn = QPushButton("导出选中")
        self.export_btn.setStyleSheet(button_style("secondary"))
        self.export_btn.clicked.connect(lambda: self.export_requested.emit(list(self._selected_ids)))

        self.tag_btn = QPushButton("添加标签")
        self.tag_btn.setStyleSheet(button_style("secondary"))
        self.tag_btn.clicked.connect(lambda: self.tag_requested.emit(list(self._selected_ids)))

        self.clear_btn = QPushButton("×")
        self.clear_btn.setStyleSheet(button_style("ghost"))
        self.clear_btn.clicked.connect(self.clear_selection_requested.emit)

        layout.addWidget(self.delete_btn)
        layout.addWidget(self.move_btn)
        layout.addWidget(self.export_btn)
        layout.addWidget(self.tag_btn)
        layout.addWidget(self.clear_btn)

    def update_count(self, count: int):
        self.count_label.setText(f"已选择 {count} 项")

    def _set_selected_ids(self, ids):
        self._selected_ids = ids
        self.update_count(len(ids))
