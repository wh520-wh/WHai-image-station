from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFileDialog, QFrame
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QFont, QTransform, QGuiApplication

import os

from src.widgets.theme import COLORS, SPACING, RADIUS, app_font, apply_card_style, button_style, label_style, scroll_area_style


class ImageViewer(QDialog):
    def __init__(self, record: dict, parent=None):
        super().__init__(parent)
        self.record = record
        self.current_scale = 1.0
        self.current_rotation = 0
        self.fit_to_window = True
        self.original_pixmap = None
        self._setup_ui()
        self._load_image()

    def _setup_ui(self):
        self.setWindowTitle("图片预览")
        self.setMinimumSize(860, 640)
        self.setStyleSheet(f"background: {COLORS['background']};")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        top_bar = QHBoxLayout()
        title_text = self.record.get("prompt", "图片预览") or "图片预览"
        title = QLabel(title_text[:64] + ("..." if len(title_text) > 64 else ""))
        title.setFont(app_font(14, QFont.Bold))
        title.setStyleSheet(label_style("title"))
        top_bar.addWidget(title)
        top_bar.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.setFixedSize(70, 36)
        close_btn.setStyleSheet(button_style("secondary"))
        close_btn.clicked.connect(self.close)
        top_bar.addWidget(close_btn)
        main_layout.addLayout(top_bar)

        image_frame = QFrame()
        image_frame.setProperty("imageMakerImageFrame", True)
        image_frame.setStyleSheet(f"""
            QFrame[imageMakerImageFrame="true"] {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #DDF7FC,
                    stop:0.55 #FFF8EC,
                    stop:1 #FFE2C8);
                border: 1px solid {COLORS['border_strong']};
                border-radius: {RADIUS['card']}px;
            }}
        """)
        image_layout = QVBoxLayout(image_frame)
        image_layout.setContentsMargins(*(SPACING['sm'],)*4)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_area.setStyleSheet(scroll_area_style())

        self.image_label = QLabel("图片不存在或尚未加载")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet(f"color: {COLORS['border_strong']}; font-size: 13px;")
        self.scroll_area.setWidget(self.image_label)
        image_layout.addWidget(self.scroll_area)
        main_layout.addWidget(image_frame, 1)

        bottom_frame = QFrame()
        apply_card_style(bottom_frame)
        bottom_bar = QHBoxLayout(bottom_frame)
        bottom_bar.setContentsMargins(*(SPACING['md'],)*4)
        bottom_bar.setSpacing(SPACING['sm'])

        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setFixedSize(36, 36)
        zoom_out_btn.setToolTip("缩小 (Ctrl+-)")
        zoom_out_btn.setStyleSheet(button_style("secondary") + "QPushButton { padding: 0; font-size: 18px; }")
        zoom_out_btn.clicked.connect(self._zoom_out)
        bottom_bar.addWidget(zoom_out_btn)

        fit_btn = QPushButton("适应窗口")
        fit_btn.setFixedSize(82, 36)
        fit_btn.setToolTip("使图片适应窗口大小")
        fit_btn.setStyleSheet(button_style("secondary"))
        fit_btn.clicked.connect(self._fit_window)
        bottom_bar.addWidget(fit_btn)

        original_btn = QPushButton("原始大小")
        original_btn.setFixedSize(82, 36)
        original_btn.setToolTip("显示原始大小 (100%)")
        original_btn.setStyleSheet(button_style("secondary"))
        original_btn.clicked.connect(self._original_size)
        bottom_bar.addWidget(original_btn)

        self.zoom_label = QLabel("100%")
        self.zoom_label.setAlignment(Qt.AlignCenter)
        self.zoom_label.setStyleSheet(label_style("section"))
        self.zoom_label.setFixedWidth(56)
        bottom_bar.addWidget(self.zoom_label)

        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setFixedSize(36, 36)
        zoom_in_btn.setStyleSheet(button_style("secondary") + "QPushButton { padding: 0; font-size: 18px; }")
        zoom_in_btn.clicked.connect(self._zoom_in)
        bottom_bar.addWidget(zoom_in_btn)

        rotate_btn = QPushButton("旋转")
        rotate_btn.setFixedSize(68, 36)
        rotate_btn.setToolTip("顺时针旋转 90°")
        rotate_btn.setStyleSheet(button_style("secondary"))
        rotate_btn.clicked.connect(self._rotate)
        bottom_bar.addWidget(rotate_btn)

        meta = self._metadata_text()
        self.meta_label = QLabel(meta)
        self.meta_label.setStyleSheet(label_style("muted"))
        bottom_bar.addWidget(self.meta_label, 1)

        save_btn = QPushButton("另存为")
        save_btn.setFixedSize(82, 36)
        save_btn.setToolTip("将当前图片另存为文件")
        save_btn.setStyleSheet(button_style("primary"))
        save_btn.clicked.connect(self._save_as)
        bottom_bar.addWidget(save_btn)

        copy_btn = QPushButton("复制")
        copy_btn.setFixedSize(70, 36)
        copy_btn.setToolTip("将图片复制到剪贴板")
        copy_btn.setStyleSheet(button_style("secondary"))
        copy_btn.clicked.connect(self._copy_to_clipboard)
        bottom_bar.addWidget(copy_btn)
        main_layout.addWidget(bottom_frame)

    def _metadata_text(self) -> str:
        platform = self.record.get("platform_id", "未知平台")
        status = self.record.get("status", "")
        return f"平台：{platform}  状态：{status}" if status else f"平台：{platform}"

    def _load_image(self):
        image_path = self.record.get("image_path")
        if image_path and os.path.exists(image_path):
            self.original_pixmap = QPixmap(image_path)
            self._update_display()

    def _update_display(self):
        if self.original_pixmap:
            transform = QTransform().rotate(self.current_rotation)
            transformed = self.original_pixmap.transformed(transform)
            if self.fit_to_window:
                viewport = self.scroll_area.viewport().size()
                scaled = transformed.scaled(
                    max(1, viewport.width() - 24),
                    max(1, viewport.height() - 24),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                self.current_scale = min(
                    scaled.width() / transformed.width() if transformed.width() else 1,
                    scaled.height() / transformed.height() if transformed.height() else 1,
                )
            else:
                scaled = transformed.scaled(
                    int(transformed.width() * self.current_scale),
                    int(transformed.height() * self.current_scale),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            self.image_label.setPixmap(scaled)
            self.image_label.setText("")
            self.zoom_label.setText(f"{int(self.current_scale * 100)}%")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.fit_to_window:
            self._update_display()

    def _zoom_in(self):
        self.fit_to_window = False
        self.current_scale = min(3.0, self.current_scale + 0.1)
        self._update_display()

    def _zoom_out(self):
        self.fit_to_window = False
        self.current_scale = max(0.1, self.current_scale - 0.1)
        self._update_display()

    def _fit_window(self):
        self.fit_to_window = True
        self._update_display()

    def _original_size(self):
        self.fit_to_window = False
        self.current_scale = 1.0
        self._update_display()

    def _rotate(self):
        self.current_rotation = (self.current_rotation + 90) % 360
        self._update_display()

    def _save_as(self):
        if not self.original_pixmap:
            return
        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存图片", "", "图片文件 (*.png *.jpg *.jpeg)"
        )
        if save_path:
            self.original_pixmap.save(save_path)

    def _copy_to_clipboard(self):
        if self.original_pixmap:
            clipboard = QGuiApplication.clipboard()
            clipboard.setPixmap(self.original_pixmap)
