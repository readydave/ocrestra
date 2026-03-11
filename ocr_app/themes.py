from __future__ import annotations

import sys

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

DEFAULT_PRIMARY_ACCENT = QColor("#0078d4")


def _system_font_stack() -> str:
    if sys.platform.startswith("win"):
        return '"Aptos", "Segoe UI Variable", "Segoe UI", sans-serif'
    if sys.platform == "darwin":
        return '"SF Pro Text", ".AppleSystemUIFont", "Helvetica Neue", sans-serif'
    return '"IBM Plex Sans", "Ubuntu", "Noto Sans", "DejaVu Sans", sans-serif'


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
QFrame#AppShell {{
    background: {shell_bg};
    border: 1px solid {border};
    border-radius: 18px;
}}
QFrame#TopBar {{
    background: {topbar_bg};
    border-bottom: 1px solid {border};
    border-top-left-radius: 18px;
    border-top-right-radius: 18px;
}}
QLabel#BrandBadge {{
    background: {accent};
    color: #ffffff;
    border-radius: 10px;
    font-size: 11px;
    font-weight: 800;
}}
QLabel#BrandTitle {{
    font-size: 24px;
    font-weight: 700;
    letter-spacing: 0.1px;
}}
QToolButton#NavButton {{
    border: 1px solid transparent;
    border-radius: 10px;
    background: transparent;
    color: {muted};
    font-size: 13px;
    font-weight: 600;
    padding: 7px 12px;
}}
QToolButton#NavButton:hover {{
    color: {text};
    background: {subtle_fill};
    border-color: {border_soft};
}}
QToolButton#NavButton::menu-indicator {{
    image: none;
    width: 0px;
    height: 0px;
}}
QToolButton#InfoButton {{
    border: 1px solid {border_soft};
    border-radius: 11px;
    background: {subtle_fill};
    color: {muted};
    font-size: 11px;
    font-weight: 700;
}}
QToolButton#InfoButton:hover {{
    color: {text};
    border-color: {button_hover_border};
    background: {button_hover_bg};
}}
QLabel#HeaderAvatar {{
    background: {card_alt};
    border: 1px solid {border_soft};
    border-radius: 16px;
}}
QFrame#DropZone {{
    border: 2px dashed {border_soft};
    border-radius: 16px;
    min-height: 152px;
    background: {card_alt};
}}
QFrame#DropZone[hover="true"] {{
    border: 2px solid {accent};
    background: {accent_soft};
}}
QLabel#DropZoneIcon {{
    background: {subtle_fill};
    border: 1px solid {border_soft};
    border-radius: 16px;
    color: {muted};
    font-size: 12px;
    font-weight: 700;
    min-width: 56px;
    min-height: 56px;
}}
QLabel#DropZoneSub {{
    color: {muted};
    font-size: 12px;
}}
QWidget#SidebarPanel {{
    background: {sidebar_bg};
}}
QScrollArea#SidebarScrollArea {{
    background: {sidebar_bg};
    border: none;
}}
QWidget#WorkspacePane {{
    background: {workspace_bg};
}}
QWidget#TableCellContainer {{
    background: transparent;
}}
QLabel#SectionEyebrow {{
    color: {muted};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QFrame#CollapsibleSection {{
    border: 1px solid {border};
    border-radius: 12px;
    background: {card_bg};
    padding: 10px;
}}
QToolButton#SectionToggle {{
    border: none;
    background: transparent;
    font-weight: 600;
    padding: 2px 0;
}}
QLabel#ParallelHint {{
    color: {muted};
    line-height: 1.35em;
}}
QPushButton {{
    background: {button_bg};
    border: 1px solid {button_border};
    border-radius: 10px;
    min-height: 34px;
    padding: 8px 14px;
    font-weight: 600;
}}
QPushButton:hover {{
    background: {button_hover_bg};
    border-color: {button_hover_border};
}}
QPushButton:disabled {{
    color: {muted};
    border-color: {border};
    background: {disabled_bg};
}}
QPushButton#StartButton {{
    background: {accent};
    border-color: {accent};
    color: #ffffff;
    font-weight: 700;
    min-width: 110px;
}}
QPushButton#StartButton:hover {{
    background: {accent_hover};
    border-color: {accent_hover};
}}
QPushButton#ExitButton {{
    background: {subtle_fill};
    border-color: {border_soft};
    color: {text};
    font-weight: 600;
}}
QPushButton#ExitButton:hover {{
    background: {button_hover_bg};
    border-color: {button_hover_border};
}}
QPushButton#SidebarButton,
QPushButton#QueueUtilityButton {{
    background: {subtle_fill};
    border-color: {border};
}}
QPushButton#SidebarButton:hover,
QPushButton#QueueUtilityButton:hover {{
    background: {button_hover_bg};
    border-color: {button_hover_border};
}}
QPushButton#TableLogButton,
QPushButton#TableActionButton {{
    background: {table_button_bg};
    border: 1px solid {table_button_border};
    border-radius: 9px;
    padding: 2px 8px;
    min-height: 24px;
}}
QPushButton#TableLogButton:hover,
QPushButton#TableActionButton:hover {{
    background: {table_button_hover_bg};
    border-color: {button_hover_border};
}}
QPushButton#TableActionButton[tone="danger"] {{
    color: {danger};
    border-color: {danger_border};
}}
QPushButton#TableActionButton[tone="danger"]:hover {{
    background: {danger_soft};
    border-color: {danger};
}}
QPlainTextEdit#LogView, QSpinBox, QComboBox {{
    background: {card_alt};
    border: 1px solid {border};
    border-radius: 12px;
    min-height: 32px;
    padding: 8px 12px;
}}
QHeaderView::section {{
    background: {header_bg};
    color: {muted};
    border: none;
    border-bottom: 1px solid {border};
    padding: 12px 14px;
    font-size: 11px;
    font-weight: 700;
}}
QTableWidget#QueueTable {{
    background: transparent;
    border: none;
    gridline-color: transparent;
}}
QTableWidget#QueueTable::item {{
    padding: 8px 12px;
    border-bottom: 1px solid {row_divider};
}}
QTableWidget#QueueTable::item:selected {{
    background: {selection_bg};
    color: {text};
}}
QProgressBar {{
    border: none;
    border-radius: 6px;
    text-align: center;
    background: {track_bg};
}}
QComboBox {{
    padding: 8px 40px 8px 12px;
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 30px;
    border-left: 1px solid {border_soft};
    background: {subtle_fill};
    border-top-right-radius: 12px;
    border-bottom-right-radius: 12px;
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
    background: {subtle_fill};
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
    border-radius: 16px;
    background: {card_bg};
}}
QFrame#RuntimeCard {{
    border: 1px solid {border};
    border-radius: 12px;
    background: {card_alt};
}}
QLabel#MetricsTitle,
QLabel#QueueTitle,
QLabel#LogTitle {{
    font-size: 20px;
    font-weight: 700;
}}
QLabel#RuntimeCardLabel {{
    color: {muted};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#RuntimeCardValue {{
    font-size: 22px;
    font-weight: 700;
}}
QLabel#RuntimeCardSub,
QLabel#MetricSummary,
QLabel#BatchCaption,
QLabel#BatchMeta {{
    color: {muted};
}}
QLabel#BatchCaption {{
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#BatchPercent {{
    color: {accent};
    font-weight: 700;
}}
QLabel#QueueBadgeActive,
QLabel#QueueBadgeMuted {{
    padding: 4px 10px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: 700;
}}
QLabel#QueueBadgeActive {{
    background: {accent_soft};
    color: {accent};
    border: 1px solid {accent_border};
}}
QLabel#QueueBadgeMuted {{
    background: {subtle_fill};
    color: {muted};
    border: 1px solid {border};
}}
QWidget#QueueEmptyState {{
    background: transparent;
}}
QFrame#EmptyStateCard {{
    background: {card_alt};
    border: 1px dashed {border_soft};
    border-radius: 16px;
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
QFrame#QueueCard,
QFrame#LogCard {{
    background: {card_bg};
    border: 1px solid {border};
    border-radius: 16px;
}}
QMenu {{
    background: {menu_bg};
    border: 1px solid {menu_border};
    border-radius: 10px;
}}
QMenu::item {{
    padding: 7px 18px;
}}
QMenu::item:selected {{
    background: {accent};
    color: #ffffff;
}}
QSplitter::handle {{
    background: {border};
}}
QSplitter::handle:horizontal {{
    width: 6px;
}}
QSplitter::handle:vertical {{
    height: 6px;
}}
QSplitter::handle:hover {{
    background: {accent};
}}
QScrollBar:vertical {{
    background: {scrollbar_track};
    width: 10px;
    margin: 4px;
}}
QScrollBar::handle:vertical {{
    background: {scrollbar_thumb};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical,
QScrollBar:horizontal,
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {{
    background: transparent;
    border: none;
    width: 0px;
    height: 0px;
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
                "bg": "#09111c",
                "text": "#e8eef7",
                "muted": "#7f92ab",
                "shell_bg": "#0d1723",
                "topbar_bg": "#101b29",
                "sidebar_bg": "#111a26",
                "workspace_bg": "#0c1520",
                "card_bg": "#111f2c",
                "card_alt": "#0c1825",
                "header_bg": "#162536",
                "border": "#213246",
                "border_soft": "#31465d",
                "row_divider": "#1a2a3a",
                "accent_soft": "#0d2c4d",
                "accent_border": "#245a92",
                "subtle_fill": "#172434",
                "button_bg": "#1a2838",
                "button_border": "#29405a",
                "button_hover_bg": "#21344b",
                "button_hover_border": "#37506d",
                "disabled_bg": "#111925",
                "popup_bg": "#152334",
                "popup_border": "#345170",
                "menu_bg": "#122031",
                "menu_border": "#324b66",
                "track_bg": "#223248",
                "table_button_bg": "#1a2a3c",
                "table_button_border": "#35506f",
                "table_button_hover_bg": "#223751",
                "selection_bg": "#16304d",
                "danger_soft": "#33171c",
                "danger_border": "#7d3942",
                "scrollbar_thumb": "#2d4159",
                "scrollbar_track": "#0d1825",
            }
        )
    else:
        base.update(
            {
                "bg": "#edf3f8",
                "text": "#182433",
                "muted": "#6b8096",
                "shell_bg": "#f8fbff",
                "topbar_bg": "#ffffff",
                "sidebar_bg": "#f6f9fd",
                "workspace_bg": "#eef3f9",
                "card_bg": "#ffffff",
                "card_alt": "#f7fbff",
                "header_bg": "#f4f7fb",
                "border": "#d5e0ec",
                "border_soft": "#e3ebf4",
                "row_divider": "#ecf1f6",
                "accent_soft": "#e8f1fb",
                "accent_border": accent.lighter(135).name(),
                "subtle_fill": "#eef4fa",
                "button_bg": "#eff4fa",
                "button_border": "#c7d6e6",
                "button_hover_bg": "#e6eef7",
                "button_hover_border": "#afc3d8",
                "disabled_bg": "#f2f5f8",
                "popup_bg": "#ffffff",
                "popup_border": "#b8c9dc",
                "menu_bg": "#ffffff",
                "menu_border": "#c5d3e2",
                "track_bg": "#e3ebf4",
                "table_button_bg": "#f3f7fb",
                "table_button_border": "#d4e0ec",
                "table_button_hover_bg": "#e9f0f7",
                "selection_bg": "#e8f1fb",
                "danger_soft": "#fff1f2",
                "danger_border": "#f1b5bb",
                "scrollbar_thumb": "#b8c8d8",
                "scrollbar_track": "#eef4fa",
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
