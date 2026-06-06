from collections import deque
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QGridLayout,
    QFrame, QPushButton, QApplication, QMenu, QLineEdit, QComboBox, QMessageBox,
    QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer, QUrl
from datetime import datetime, timedelta
from PySide6.QtGui import QPixmap, QPixmapCache, QFont, QDesktopServices

import os

from src.widgets.theme import COLORS, RADIUS, SPACING, app_font, apply_card_style, button_style, compact_input_style, label_style, make_empty_state_label, scroll_area_style


class HistoryPanel(QWidget):
    image_selected = Signal(dict)
    reuse_requested = Signal(dict)
    delete_requested = Signal(dict)
    batch_selection_changed = Signal(set)

    def __init__(self, history_manager, parent=None):
        super().__init__(parent)
        self.history_manager = history_manager
        self.history: deque[dict] = deque()
        self.view_mode = "grid"
        self._batch_mode = False
        self._selected_ids: set[str] = set()
        self._search_debounce_timer = QTimer()
        self._search_debounce_timer.setSingleShot(True)
        self._search_debounce_timer.timeout.connect(self._apply_filters)
        self._current_search_text = ""
        self._current_platform = "全部"
        self._current_date_range = "全部"
        self._current_sort = "时间倒序"
        QPixmapCache.setCacheLimit(51200)
        self._setup_ui()
        self._dpi_scale = self.logicalDpiX() / 96.0

    def _setup_ui(self):
        apply_card_style(self)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(SPACING['md'])

        self.title_layout = QHBoxLayout()
        self.title_layout.setContentsMargins(0, 0, 0, 0)
        self.title_layout.setSpacing(SPACING['sm'])
        title = QLabel("历史画廊")
        title.setStyleSheet(label_style("title"))
        self.title_layout.addWidget(title)

        self.count_label = QLabel("共 0 张")
        self.count_label.setStyleSheet(label_style("muted"))
        self.title_layout.addWidget(self.count_label)
        self.title_layout.addStretch()
        main_layout.addLayout(self.title_layout)

        # 工具栏：搜索 + 筛选 + 视图切换 + 操作按钮
        self.toolbar_frame = QFrame()
        self.toolbar_frame.setMinimumHeight(154)
        self.toolbar_frame.setStyleSheet("QFrame { background: transparent; border: none; }")
        toolbar_layout = QVBoxLayout(self.toolbar_frame)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(SPACING['sm'])

        self.search_toolbar_frame = QFrame()
        self.search_toolbar_frame.setStyleSheet("QFrame { background: transparent; border: none; }")
        search_layout = QHBoxLayout(self.search_toolbar_frame)
        search_layout.setContentsMargins(0, 0, SPACING['sm'], 0)
        search_layout.setSpacing(SPACING['sm'])

        self.filter_toolbar_frame = QFrame()
        self.filter_toolbar_frame.setStyleSheet("QFrame { background: transparent; border: none; }")
        filter_layout = QHBoxLayout(self.filter_toolbar_frame)
        filter_layout.setContentsMargins(0, 0, SPACING['sm'], 0)
        filter_layout.setSpacing(SPACING['sm'])

        self.sort_toolbar_frame = QFrame()
        self.sort_toolbar_frame.setStyleSheet("QFrame { background: transparent; border: none; }")
        sort_layout = QHBoxLayout(self.sort_toolbar_frame)
        sort_layout.setContentsMargins(0, 0, SPACING['sm'], 0)
        sort_layout.setSpacing(SPACING['sm'])

        self.action_toolbar_frame = QFrame()
        self.action_toolbar_frame.setStyleSheet("QFrame { background: transparent; border: none; }")
        action_layout = QHBoxLayout(self.action_toolbar_frame)
        action_layout.setContentsMargins(0, 0, SPACING['sm'], 0)
        action_layout.setSpacing(SPACING['sm'])

        # 搜索输入
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索...")
        self.search_input.setToolTip("搜索提示词关键词")
        self.search_input.setMinimumWidth(96)
        self.search_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.search_input.setStyleSheet(compact_input_style())
        self.search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_input)

        # 筛选下拉
        self.platform_filter = QComboBox()
        self.platform_filter.addItem("全部")
        self.platform_filter.setToolTip("按平台筛选")
        self.platform_filter.setMinimumWidth(88)
        self.platform_filter.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.platform_filter.setStyleSheet(compact_input_style())
        self.platform_filter.currentTextChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.platform_filter)

        self.date_filter = QComboBox()
        self.date_filter.addItems(["全部", "今天", "本周", "本月"])
        self.date_filter.setToolTip("按时间范围筛选")
        self.date_filter.setMinimumWidth(82)
        self.date_filter.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.date_filter.setStyleSheet(compact_input_style())
        self.date_filter.currentTextChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.date_filter)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["时间倒序", "时间正序", "按平台"])
        self.sort_combo.setToolTip("排序方式")
        self.sort_combo.setMinimumWidth(118)
        self.sort_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.sort_combo.setStyleSheet(compact_input_style())
        self.sort_combo.currentTextChanged.connect(self._on_sort_changed)
        sort_layout.addWidget(self.sort_combo)

        filter_layout.addStretch()

        # 视图切换
        self.grid_mode_btn = QPushButton("网格")
        self.grid_mode_btn.setMinimumWidth(48)
        self.grid_mode_btn.setToolTip("以网格形式查看缩略图")
        self.grid_mode_btn.setStyleSheet(button_style("ghost"))
        self.grid_mode_btn.clicked.connect(lambda: self.set_view_mode("grid"))
        action_layout.addWidget(self.grid_mode_btn)

        self.single_mode_btn = QPushButton("单列")
        self.single_mode_btn.setMinimumWidth(48)
        self.single_mode_btn.setToolTip("以大图单列形式查看")
        self.single_mode_btn.setStyleSheet(button_style("ghost"))
        self.single_mode_btn.clicked.connect(lambda: self.set_view_mode("single"))
        action_layout.addWidget(self.single_mode_btn)

        # 操作按钮
        self.clear_btn = QPushButton("清空")
        self.clear_btn.setMinimumWidth(48)
        self.clear_btn.setToolTip("清空所有历史记录（不可撤销）")
        self.clear_btn.setStyleSheet(button_style("danger_ghost"))
        self.clear_btn.clicked.connect(self._clear_history)
        action_layout.addWidget(self.clear_btn)

        self.clean_invalid_btn = QPushButton("清理无效")
        self.clean_invalid_btn.setMinimumWidth(64)
        self.clean_invalid_btn.setToolTip("删除图片文件已丢失的历史记录")
        self.clean_invalid_btn.setStyleSheet(button_style("danger_ghost"))
        self.clean_invalid_btn.clicked.connect(self._clean_invalid_records)
        action_layout.addWidget(self.clean_invalid_btn)

        action_layout.addStretch()
        toolbar_layout.addWidget(self.search_toolbar_frame)
        toolbar_layout.addWidget(self.filter_toolbar_frame)
        toolbar_layout.addWidget(self.sort_toolbar_frame)
        toolbar_layout.addWidget(self.action_toolbar_frame)

        main_layout.addWidget(self.toolbar_frame)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(scroll_area_style())

        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setHorizontalSpacing(SPACING['lg'])
        self.grid_layout.setVerticalSpacing(SPACING['lg'])
        self.grid_layout.setContentsMargins(0, 0, 16, 0)

        self.scroll_area.setWidget(self.grid_widget)
        main_layout.addWidget(self.scroll_area, 1)



    def load_history(self, records: list[dict] | None = None):
        if records is not None:
            self.history = deque(records)
            self._update_grid()
            return
        # Fallback: standalone caller (before main window merges the async call)
        if not self.history_manager:
            self.history = deque()
            self._update_grid()
            return
        from src.config.event_loop import run_async

        try:
            async def _load():
                return await self.history_manager.get_history(100)
            self.history = deque(run_async(_load()))
        except Exception:
            self.history = deque()
        self._update_grid()

    def _update_grid(self, records: list[dict] | None = None):
        if records is None:
            records = self.history

        display_history = [r for r in records if self._record_has_image(r)]

        # Determine target widget size based on view_mode (DPI-scaled)
        if self.view_mode == "single":
            target_w, target_h = int(220 * self._dpi_scale), int(164 * self._dpi_scale)
        else:
            target_w, target_h = int(108 * self._dpi_scale), int(128 * self._dpi_scale)

        # Collect existing widgets, checking for view_mode mismatch (full rebuild needed)
        existing_items = {}
        needs_full_rebuild = False
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w is None:
                continue
            task_id = getattr(w, '_task_id', None)
            if task_id is None:
                # Empty-state labels and other non-item widgets
                w.deleteLater()
            else:
                if w.width() != target_w or w.height() != target_h:
                    needs_full_rebuild = True
                w.setVisible(False)
                existing_items[w._task_id] = w

        if needs_full_rebuild:
            for w in existing_items.values():
                w.deleteLater()
            existing_items.clear()

        if not display_history:
            empty = make_empty_state_label("暂无历史图片\n生成完成后会出现在这里")
            self.grid_layout.addWidget(empty, 0, 0, 1, 2)
        else:
            columns = 1 if self.view_mode == "single" else 2
            for index, record in enumerate(display_history):
                row = index // columns
                col = index % columns
                thumb_path = record.get("thumbnail_path") or record.get("image_path")
                if not thumb_path or not os.path.exists(thumb_path):
                    thumb_path = None
                item = self._try_reuse_existing_widget(record, existing_items)
                if item is None:
                    item = self._create_image_item(record, thumb_path)
                else:
                    item.setVisible(True)
                self.grid_layout.addWidget(item, row, col)

            # Clean up unused widgets
            for w in existing_items.values():
                w.deleteLater()

        self.count_label.setText(f"共 {len(display_history)} 张")

        self._refresh_platform_filter_options()

    def _try_reuse_existing_widget(self, record: dict, existing: dict) -> QFrame | None:
        """Try to find and return an existing widget by task_id."""
        task_id = record.get("task_id")
        w = existing.pop(task_id, None)
        if w:
            w.setVisible(True)
        return w

    def _record_has_image(self, record: dict) -> bool:
        image_path = record.get("image_path")
        thumbnail_path = record.get("thumbnail_path")
        return bool(image_path or thumbnail_path)

    def _create_image_item(self, record: dict, thumb_path: str | None) -> QFrame:
        frame = QFrame()
        frame.setProperty("imageMakerHistoryItem", True)
        if self.view_mode == "single":
            frame.setFixedSize(int(220 * self._dpi_scale), int(164 * self._dpi_scale))
        else:
            frame.setFixedSize(int(108 * self._dpi_scale), int(128 * self._dpi_scale))

        has_recorded_path = bool(record.get("thumbnail_path") or record.get("image_path"))
        file_missing = has_recorded_path and (thumb_path is None or (thumb_path and not os.path.exists(thumb_path)))
        border_color = COLORS['warning'] if file_missing else COLORS['border']

        frame.setStyleSheet(f"""
            QFrame[imageMakerHistoryItem="true"] {{
                background: {COLORS['panel']};
                border: 1px solid {border_color};
                border-radius: {RADIUS['card']}px;
            }}
            QFrame[imageMakerHistoryItem="true"]:hover {{
                border: 2px solid {COLORS['accent']};
                background: {COLORS['sky_soft']};
            }}
        """)
        frame.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(SPACING['sm'], SPACING['sm'], SPACING['sm'], SPACING['sm'])
        layout.setSpacing(SPACING['sm'])

        label = QLabel()
        label.setAlignment(Qt.AlignCenter)
        if self.view_mode == "single":
            label.setFixedSize(int(204 * self._dpi_scale), int(140 * self._dpi_scale))
        else:
            label.setFixedSize(int(92 * self._dpi_scale), int(108 * self._dpi_scale))
        if thumb_path and os.path.exists(thumb_path):
            if self.view_mode == "single":
                target_w = int(202 * self._dpi_scale)
                target_h = int(138 * self._dpi_scale)
            else:
                target_w = int(90 * self._dpi_scale)
                target_h = int(106 * self._dpi_scale)
            cached_key = f"thumb_{thumb_path}_{target_w}x{target_h}"
            pixmap = QPixmapCache.find(cached_key)
            if not pixmap:
                pixmap = QPixmap(thumb_path).scaled(
                    target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation,
                )
                QPixmapCache.insert(cached_key, pixmap)
            label.setPixmap(pixmap)
        elif file_missing:
            label.setText("文件缺失")
            label.setStyleSheet(f"color: {COLORS['warning']}; font-size: 10px; border: 1px dashed {COLORS['warning']}; border-radius: {RADIUS['compact']}px;")
        else:
            label.setText("图片")
            label.setStyleSheet(f"color: {COLORS['subtle']}; font-size: 12px;")
        layout.addWidget(label)

        frame.setFocusPolicy(Qt.StrongFocus)
        frame.mousePressEvent = lambda event, r=record: self.image_selected.emit(r)
        frame.keyPressEvent = lambda event, r=record, w=frame: self._handle_item_key(event, r, w)
        frame.setContextMenuPolicy(Qt.CustomContextMenu)
        frame.customContextMenuRequested.connect(lambda pos, r=record, w=frame: self._show_record_menu(r, w, pos))
        frame._task_id = record.get("task_id")
        return frame

    def _handle_item_key(self, event, record, widget):
        if event.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Space):
            self.image_selected.emit(record)
        elif event.key() == Qt.Key_Menu or (event.key() == Qt.Key_F10 and event.modifiers() == Qt.ShiftModifier):
            self._show_record_menu(record, widget, widget.rect().bottomLeft())


    def _show_record_menu(self, record: dict, widget: QWidget, pos):
        menu = QMenu(widget)
        preview_action = menu.addAction("预览")
        reuse_action = menu.addAction("复用参数")
        copy_action = menu.addAction("复制路径")
        folder_action = menu.addAction("打开文件夹")
        delete_action = menu.addAction("删除记录")
        action = menu.exec(widget.mapToGlobal(pos))
        if action == preview_action:
            self.image_selected.emit(record)
        elif action == reuse_action:
            self.request_reuse(record)
        elif action == copy_action:
            QApplication.clipboard().setText(record.get("image_path") or "")
        elif action == folder_action:
            path = record.get("image_path") or ""
            if path:
                self._open_in_file_manager(path)
        elif action == delete_action:
            reply = QMessageBox.question(
                widget, "确认删除", "确定要删除这条历史记录吗？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.delete_requested.emit(record)

    def _open_in_file_manager(self, file_path: str) -> None:
        """Open the folder containing the given file in the OS file manager.

        Cross-platform: uses QDesktopServices, works on Windows, macOS, and Linux.
        """
        folder = os.path.dirname(file_path)
        if folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def set_view_mode(self, mode: str):
        self.view_mode = "single" if mode == "single" else "grid"
        self._update_grid()

    def toggle_batch_mode(self):
        """Toggle batch selection mode."""
        self._batch_mode = not self._batch_mode
        if not self._batch_mode:
            self._selected_ids.clear()
        self.batch_selection_changed.emit(self._selected_ids)

    def enter_batch_mode(self):
        """Enter batch selection mode."""
        self._batch_mode = True
        self.batch_selection_changed.emit(self._selected_ids)

    def exit_batch_mode(self):
        """Exit batch selection mode and clear selection."""
        self._batch_mode = False
        self._selected_ids.clear()
        self.batch_selection_changed.emit(self._selected_ids)

    def request_reuse(self, record: dict):
        self.reuse_requested.emit(record)

    def _clear_history(self):
        reply = QMessageBox.question(
            self, "确认清空", "确定要清空所有历史记录吗？此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        from src.config.event_loop import run_async

        if self.history_manager:
            for record in list(self.history):
                task_id = record.get("task_id")
                if task_id:

                    async def _delete():
                        await self.history_manager.delete_record(task_id)
                    run_async(_delete())

        self.history = deque()
        self._update_grid()

    def add_record(self, record: dict):
        self.history.appendleft(record)
        if self._has_active_filters():
            self._apply_filters()
        else:
            self._update_grid()

    def _has_active_filters(self) -> bool:
        return bool(
            self._current_search_text
            or self._current_platform != "全部"
            or self._current_date_range != "全部"
            or self._current_sort != "时间倒序"
        )

    def _refresh_platform_filter_options(self):
        existing_platforms = sorted({
            r.get("platform_id", "未知") or "未知"
            for r in self.history
            if r.get("platform_id")
        })
        current_text = self.platform_filter.currentText()
        self.platform_filter.blockSignals(True)
        self.platform_filter.clear()
        self.platform_filter.addItem("全部")
        for p in existing_platforms:
            if p != "全部":
                self.platform_filter.addItem(p)
        idx = self.platform_filter.findText(current_text)
        self.platform_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.platform_filter.blockSignals(False)
        self._current_platform = self.platform_filter.currentText()

    def _clean_invalid_records(self):
        from src.config.event_loop import run_async

        invalid = []
        for record in self.history:
            image_path = record.get("image_path")
            thumbnail_path = record.get("thumbnail_path")
            has_recorded_path = bool(image_path or thumbnail_path)
            if not has_recorded_path:
                continue
            has_file = (image_path and os.path.exists(image_path)) or \
                       (thumbnail_path and os.path.exists(thumbnail_path))
            if not has_file:
                invalid.append(record)

        if not invalid:
            return

        reply = QMessageBox.question(
            self, "确认清理", f"发现 {len(invalid)} 条图片文件已丢失的记录，确定删除吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        for record in invalid:
            task_id = record.get("task_id")
            if task_id and self.history_manager:
                async def _del(tid=task_id):
                    await self.history_manager.delete_record(tid)
                run_async(_del())

        self.load_history()

    def _on_search_changed(self, text: str):
        self._current_search_text = text
        self._search_debounce_timer.start(300)

    def _on_filter_changed(self):
        self._current_platform = self.platform_filter.currentText()
        self._current_date_range = self.date_filter.currentText()
        self._apply_filters()

    def _on_sort_changed(self):
        self._current_sort = self.sort_combo.currentText()
        self._apply_filters()

    def _apply_filters(self):
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        search_text = self._current_search_text
        platform = self._current_platform
        date_range = self._current_date_range

        # Date threshold pre-computation
        date_threshold = None
        if date_range == "今天":
            date_threshold = today_start
        elif date_range == "本周":
            date_threshold = week_start
        elif date_range == "本月":
            date_threshold = month_start

        # Single-pass filtering
        filtered = []
        for r in self.history:
            if search_text and not (
                search_text in str(r.get("prompt", "")) or
                search_text in str(r.get("platform_id", "")) or
                search_text in str(r.get("model", ""))
            ):
                continue
            if platform != "全部" and r.get("platform_id") != platform:
                continue
            if date_threshold is not None and self._record_date(r) < date_threshold:
                continue
            filtered.append(r)

        # Sort
        sort = self._current_sort
        if sort == "时间倒序":
            filtered.sort(key=lambda r: self._record_date(r), reverse=True)
        elif sort == "时间正序":
            filtered.sort(key=lambda r: self._record_date(r), reverse=False)
        elif sort == "按平台":
            filtered.sort(key=lambda r: str(r.get("platform_id", "")))

        self._update_grid(filtered)

    def _record_date(self, record: dict) -> datetime:
        timestamp = record.get("created_at") or record.get("timestamp") or 0
        if isinstance(timestamp, (int, float)):
            return datetime.fromtimestamp(timestamp)
        return datetime.min

