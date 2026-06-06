"""Shared visual theme for imageMaker widgets."""

from __future__ import annotations

from PySide6.QtGui import QFont


COLORS = {
    "sky": "#48C6F0",
    "sky_soft": "#DDF7FC",
    "background": "#F7EFE2",
    "panel": "#FFF8EC",
    "panel_alt": "#FFF0D6",
    "glass": "rgba(255, 248, 236, 0.88)",
    "border": "#E8D0B0",
    "border_strong": "#9A7030",
    "primary": "#E87828",
    "primary_hover": "#D4651E",
    "primary_pressed": "#B85A10",
    "primary_soft": "#FFE2C8",
    "primary_text": "#B05008",
    "accent": "#5BC8F0",
    "accent_hover": "#4AB8E0",
    "accent_soft": "#DDF7FC",
    "text": "#2F3538",
    "muted": "#3A4A4E",
    "subtle": "#6B7B7A",
    "success": "#329A6E",
    "success_hover": "#349679",
    "success_soft": "#DDF5EB",
    "warning": "#A85A10",
    "warning_soft": "#FFE8CC",
    "danger": "#C95855",
    "danger_soft": "#FFE3DF",
    "info": "#2EA8D7",
    "info_soft": "#DDF7FC",
    "input": "rgba(255, 255, 255, 0.72)",
    "shadow": "rgba(255, 138, 61, 0.16)",
}

COLORS["sunset"] = COLORS["primary"]
COLORS["sunset_hover"] = COLORS["primary_hover"]
COLORS["sunset_pressed"] = COLORS["primary_pressed"]
COLORS["sunset_soft"] = COLORS["primary_soft"]

SPACING = {
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 24,
}

RADIUS = {
    "compact": 8,
    "control": 12,
    "card": 18,
    "dialog": 22,
}

CARD_PROPERTY = "imageMakerCard"


def app_font(point_size: int = 11, weight: QFont.Weight = QFont.Normal) -> QFont:
    font = QFont("Microsoft YaHei UI")
    font.setPointSize(point_size)
    font.setWeight(weight)
    return font


APP_STYLESHEET = f"""
QWidget {{
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    color: {COLORS['text']};
}}
QPushButton:focus {{
    border: 1px solid {COLORS['accent']};
}}
QToolTip {{
    background: {COLORS['text']};
    color: {COLORS['panel']};
    border: none;
    border-radius: {RADIUS['compact']}px;
    padding: {SPACING['sm']}px {SPACING['md']}px;
}}
QScrollBar:vertical {{
    width: 8px;
    background: transparent;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {COLORS['primary_soft']};
    border-radius: {SPACING['xs']}px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{
    background: {COLORS['primary']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    height: 8px;
    background: transparent;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {COLORS['primary_soft']};
    border-radius: {SPACING['xs']}px;
    min-width: 32px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {COLORS['primary']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
"""


def card_style(background: str | None = None, border: str | None = None) -> str:
    return f"""
    QFrame[{CARD_PROPERTY}="true"], QWidget[{CARD_PROPERTY}="true"] {{
        background: {background or COLORS['panel']};
        border: 1px solid {border or COLORS['border']};
        border-radius: {RADIUS['card']}px;
    }}
    """


def apply_card_style(widget, background: str | None = None, border: str | None = None) -> None:
    widget.setProperty(CARD_PROPERTY, True)
    widget.setStyleSheet(card_style(background, border))


def input_style() -> str:
    return f"""
    QTextEdit, QLineEdit, QComboBox {{
        background: rgba(255, 255, 255, 0.72);
        border: 1px solid {COLORS['border']};
        border-radius: {RADIUS['control']}px;
        padding: {SPACING['sm']}px {SPACING['md']}px;
        color: {COLORS['text']};
        selection-background-color: {COLORS['primary']};
        selection-color: {COLORS['panel']};
    }}
    QTextEdit:focus, QLineEdit:focus, QComboBox:focus {{
        border: 1px solid {COLORS['accent']};
        background: #FFFFFF;
    }}
    QTextEdit:disabled, QLineEdit:disabled, QComboBox:disabled {{
        background: #F0F0F0;
        color: {COLORS['subtle']};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QLineEdit {{
        background: transparent;
        border: none;
        padding: 0;
        selection-background-color: {COLORS['primary']};
        selection-color: {COLORS['panel']};
    }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {COLORS['muted']};
        margin-right: 8px;
    }}
    """


def compact_input_style() -> str:
    """Compact input style for search/filter bars."""
    return f"""
    QLineEdit, QComboBox {{
        background: {COLORS['input']};
        border: 1px solid {COLORS['border']};
        border-radius: {RADIUS['compact']}px;
        padding: 4px 18px 4px 8px;
        font-size: 12px;
        color: {COLORS['text']};
    }}
    QLineEdit:focus, QComboBox:focus {{
        border-color: {COLORS['accent']};
    }}
    QLineEdit::placeholder {{
        color: {COLORS['subtle']};
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 16px;
        border: none;
        background: transparent;
    }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 3px solid transparent;
        border-right: 3px solid transparent;
        border-top: 4px solid {COLORS['muted']};
        margin-right: 6px;
    }}
    """


def make_empty_state_label(text: str) -> "QLabel":
    """Create a styled empty-state placeholder label."""
    from PySide6.QtWidgets import QLabel
    from PySide6.QtCore import Qt
    label = QLabel(text)
    label.setAlignment(Qt.AlignCenter)
    label.setStyleSheet(f"color: {COLORS['subtle']}; font-size: 12px; line-height: 150%;")
    return label


def button_style(kind: str = "secondary") -> str:
    if kind == "primary":
        return f"""
        QPushButton {{
            background: {COLORS['primary']};
            color: #FFFFFF;
            border: none;
            border-radius: {RADIUS['control']}px;
            padding: {SPACING['md']}px {SPACING['xl']}px;
            font-weight: 700;
        }}
        QPushButton:hover {{ background: {COLORS['primary_hover']}; }}
        QPushButton:pressed {{ background: {COLORS['primary_pressed']}; }}
        QPushButton:disabled {{ background: {COLORS['border']}; color: {COLORS['subtle']}; }}
        """
    if kind == "ghost":
        return f"""
        QPushButton {{
            background: transparent;
            color: {COLORS['muted']};
            border: none;
            border-radius: {RADIUS['compact']}px;
            padding: {SPACING['sm']}px {SPACING['sm']}px;
        }}
        QPushButton:hover {{ background: {COLORS['accent_soft']}; color: {COLORS['accent']}; }}
        QPushButton:pressed {{ background: {COLORS['sky_soft']}; color: {COLORS['sky']}; }}
        QPushButton:disabled {{ color: {COLORS['subtle']}; background: transparent; }}
        """
    if kind == "danger_ghost":
        return f"""
        QPushButton {{
            background: transparent;
            color: {COLORS['subtle']};
            border: none;
            border-radius: {RADIUS['compact']}px;
            padding: {SPACING['xs']}px {SPACING['sm']}px;
        }}
        QPushButton:hover {{ background: {COLORS['danger_soft']}; color: {COLORS['danger']}; }}
        QPushButton:pressed {{ background: {COLORS['danger']}; color: #FFFFFF; }}
        QPushButton:disabled {{ color: {COLORS['subtle']}; background: transparent; }}
        """
    if kind == "success":
        return f"""
        QPushButton {{
            background: {COLORS['success']};
            color: #FFFFFF;
            border: none;
            border-radius: {RADIUS['control']}px;
            padding: {SPACING['md']}px {SPACING['lg']}px;
            font-weight: 600;
        }}
        QPushButton:hover {{ background: {COLORS['success_hover']}; }}
        QPushButton:pressed {{ background: #2A8A5E; }}
        QPushButton:disabled {{ background: {COLORS['border']}; color: {COLORS['subtle']}; }}
        """
    return f"""
    QPushButton {{
        background: {COLORS['panel']};
        color: {COLORS['text']};
        border: 1px solid {COLORS['border']};
        border-radius: {RADIUS['control']}px;
        padding: {SPACING['sm']}px {SPACING['lg']}px;
    }}
    QPushButton:hover {{
        border-color: {COLORS['primary']};
        color: {COLORS['primary']};
        background: {COLORS['primary_soft']};
    }}
    QPushButton:pressed {{ background: {COLORS['primary_soft']}; }}
    QPushButton:disabled {{ color: {COLORS['subtle']}; background: {COLORS['panel_alt']}; }}
    """


def tab_style() -> str:
    return f"""
    QTabWidget::pane {{
        border: none;
        background: transparent;
    }}
    QTabBar::tab {{
        background: {COLORS['panel_alt']};
        color: {COLORS['muted']};
        border: 1px solid {COLORS['border']};
        border-radius: {RADIUS['control']}px;
        padding: {SPACING['sm']}px {SPACING['lg']}px;
        margin-right: 8px;
    }}
    QTabBar::tab:selected {{
        background: {COLORS['primary']};
        color: #FFFFFF;
        border-color: {COLORS['primary']};
        font-weight: 700;
    }}
    QTabBar::tab:hover:!selected {{
        background: {COLORS['primary_soft']};
        color: {COLORS['primary_text']};
    }}
    """


def scroll_area_style() -> str:
    return """
    QScrollArea {
        border: none;
        background: transparent;
    }
    QScrollArea > QWidget > QWidget {
        background: transparent;
    }
    """


def label_style(kind: str = "body") -> str:
    if kind == "title":
        return f"color: {COLORS['text']}; font-size: 16px; font-weight: 700;"
    if kind == "section":
        return f"color: {COLORS['text']}; font-size: 14px; font-weight: 700;"
    if kind == "muted":
        return f"color: {COLORS['muted']}; font-size: 12px;"
    return f"color: {COLORS['text']}; font-size: 12px;"
