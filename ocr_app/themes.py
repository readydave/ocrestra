from __future__ import annotations

import sys

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

DEFAULT_PRIMARY_ACCENT = QColor("#0078d4")


def _system_font_stack() -> str:
    if sys.platform.startswith("win"):
        return '"Segoe UI", "Segoe UI Variable", sans-serif'
    if sys.platform == "darwin":
        return '".AppleSystemUIFont", "SF Pro Text", "Helvetica Neue", sans-serif'
    return '"Ubuntu", "Noto Sans", "DejaVu Sans", sans-serif'


def _resolve_primary_accent(system_palette: QPalette) -> QColor:
    accent = system_palette.color(QPalette.Active, QPalette.Highlight)
    if not accent.isValid():
        accent = system_palette.color(QPalette.Highlight)
    if not accent.isValid() or accent.alpha() == 0 or accent.saturation() < 35:
        return QColor(DEFAULT_PRIMARY_ACCENT)
    return accent


THEME_QSS_TEMPLATE = """
QWidget {{
    background: {bg};
    color: {text};
    font-family: {font_stack};
    font-size: 13px;
}}
QLabel {{
    background: transparent;
}}
QLabel#Title {{
    font-size: 30px;
    font-weight: 700;
    letter-spacing: 0.2px;
}}
QLabel#Subtitle {{
    color: {muted};
    font-size: 14px;
}}
QFrame#DropZone {{
    border: 1px dashed {border_soft};
    border-radius: 12px;
    min-height: 150px;
    background: {panel_alt};
}}
QFrame#DropZone[hover="true"] {{
    border: 1px solid {accent};
    background: {accent_soft};
}}
QLabel#DropZoneSub {{
    color: {muted};
}}
QFrame#CollapsibleSection {{
    border: 1px solid {border};
    border-radius: 10px;
    background: {panel};
    padding: 8px;
}}
QToolButton#SectionToggle {{
    border: none;
    background: transparent;
    font-weight: 600;
    padding: 4px 0;
}}
QLabel#ParallelHint {{
    color: {muted};
}}
QPushButton {{
    background: {button_bg};
    border: 1px solid {button_border};
    border-radius: 8px;
    min-height: 32px;
    padding: 8px 14px;
}}
QPushButton:hover {{
    background: {button_hover_bg};
    border-color: {button_hover_border};
}}
QPushButton:disabled {{
    color: {muted};
    border-color: {border};
}}
QPushButton#StartButton {{
    background: {accent};
    border-color: {accent};
    color: #ffffff;
    font-weight: 700;
}}
QPushButton#StartButton:hover {{
    background: {accent_hover};
    border-color: {accent_hover};
}}
QPushButton#DangerButton {{
    background: {danger};
    border-color: {danger};
    color: #ffffff;
    font-weight: 600;
}}
QPushButton#DangerButton:hover {{
    background: {danger_hover};
    border-color: {danger_hover};
}}
QTableWidget, QPlainTextEdit, QSpinBox, QComboBox {{
    background: {panel};
    border: 1px solid {border};
    border-radius: 8px;
    min-height: 32px;
    padding: 8px 12px;
}}
QHeaderView::section {{
    background: {surface};
    border: none;
    padding: 8px 12px;
}}
QTableWidget {{
    alternate-background-color: {surface_alt};
}}
QProgressBar {{
    border: 1px solid {border};
    border-radius: 6px;
    text-align: center;
    background: {panel_alt};
}}
QComboBox {{
    padding: 8px 44px 8px 12px;
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 32px;
    border-left: 1px solid {border_soft};
    background: {surface};
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
}}
QComboBox::down-arrow {{
    image: none;
    width: 0px;
    height: 0px;
}}
QComboBox QAbstractItemView {{
    background: {popup_bg};
    border: 1px solid {popup_border};
    outline: 0;
    padding: 4px 0;
    selection-background-color: {accent};
    selection-color: #ffffff;
}}
QAbstractItemView#ComboPopupView {{
    background: {popup_bg};
    border: 1px solid {popup_border};
    selection-background-color: {accent};
    selection-color: #ffffff;
}}
QComboBox QAbstractItemView::item {{
    min-height: 28px;
    padding: 4px 10px;
}}
QSpinBox::up-button, QSpinBox::down-button {{
    width: 16px;
    background: {surface};
    border-left: 1px solid {border_soft};
}}
QSpinBox::up-arrow {{
    image: url(:/qt-project.org/styles/commonstyle/images/uparrow-16.png);
    width: 10px;
    height: 8px;
}}
QSpinBox::down-arrow {{
    image: url(:/qt-project.org/styles/commonstyle/images/downarrow-16.png);
    width: 10px;
    height: 8px;
}}
QFrame#StatsFrame {{
    border: 1px solid {border};
    border-radius: 8px;
    background: {panel_alt};
}}
QWidget#QueueEmptyState {{
    background: transparent;
}}
QFrame#EmptyStateCard {{
    background: {panel};
    border: 1px dashed {border_soft};
    border-radius: 12px;
    min-width: 320px;
}}
QLabel#EmptyStateTitle {{
    font-size: 20px;
    font-weight: 700;
}}
QLabel#EmptyStateBody {{
    color: {muted};
    font-size: 14px;
}}
QMenu {{
    background: {menu_bg};
    border: 1px solid {menu_border};
}}
QMenu::item {{
    padding: 6px 18px;
}}
QMenu::item:selected {{
    background: {accent};
    color: #ffffff;
}}
QSplitter::handle {{
    background: {border};
}}
QSplitter::handle:horizontal {{
    width: 1px;
}}
QSplitter::handle:vertical {{
    height: 1px;
}}
"""


def _theme_tokens(mode: str, system_palette: QPalette) -> dict[str, str]:
    accent = _resolve_primary_accent(system_palette)

    base = {
        "accent": accent.name(),
        "accent_hover": accent.lighter(112).name(),
        "font_stack": _system_font_stack(),
        "danger": "#b44343",
        "danger_hover": "#c65353",
    }
    if mode == "dark":
        base.update(
            {
                "bg": "#0f1724",
                "text": "#d7e1ef",
                "muted": "#9ab0c9",
                "panel": "#162338",
                "panel_alt": "#132033",
                "surface": "#1d3049",
                "surface_alt": "#1a2b43",
                "border": "#355173",
                "border_soft": "#3f5f86",
                "accent_soft": accent.lighter(185).name(),
                "button_bg": "#24405f",
                "button_border": "#5a7ea8",
                "button_hover_bg": "#2e5077",
                "button_hover_border": "#6a90bc",
                "popup_bg": "#315278",
                "popup_border": "#7fa2cd",
                "menu_bg": "#2a4568",
                "menu_border": "#6a90bc",
            }
        )
    else:
        base.update(
            {
                "bg": "#f5f8fc",
                "text": "#233347",
                "muted": "#4f6379",
                "panel": "#ffffff",
                "panel_alt": "#f7faff",
                "surface": "#edf3fb",
                "surface_alt": "#f3f7fd",
                "border": "#b8c9de",
                "border_soft": "#c9d7e8",
                "accent_soft": accent.lighter(175).name(),
                "button_bg": "#e7f0fb",
                "button_border": "#8fafcf",
                "button_hover_bg": "#d6e6f7",
                "button_hover_border": "#7f9fc0",
                "popup_bg": "#d5e5fa",
                "popup_border": "#5f83af",
                "menu_bg": "#e6f0fd",
                "menu_border": "#7898bc",
            }
        )
    return base


def build_qss(mode: str, system_palette: QPalette) -> str:
    return THEME_QSS_TEMPLATE.format(**_theme_tokens(mode, system_palette))


def apply_theme(app: QApplication, theme: str, system_palette: QPalette, system_style: str) -> None:
    mode = theme
    if theme == "system":
        mode = "dark" if system_palette.color(QPalette.Window).lightness() < 128 else "light"
        app.setStyle(system_style)
        app.setPalette(system_palette)
    else:
        app.setStyle("Fusion")
    app.setStyleSheet(build_qss(mode, system_palette))
