from __future__ import annotations

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication


DARK_STYLESHEET = """
QWidget {
    background: #161a1f;
    color: #d8dee9;
    font-family: "Noto Sans", "Cantarell", sans-serif;
    font-size: 13px;
}
QLabel#Title {
    font-size: 24px;
    font-weight: 700;
    color: #eceff4;
}
QLabel#Subtitle {
    color: #88c0d0;
}
QFrame#DropZone {
    border: 2px dashed #cf3347;
    border-radius: 12px;
    min-height: 120px;
    background: #20262d;
}
QFrame#DropZone[hover="true"] {
    border: 2px solid #3ad16b;
    background: #213126;
}
QLabel#DropZoneSub {
    color: #81a1c1;
}
QPushButton {
    background: #2e3440;
    border: 1px solid #4c566a;
    border-radius: 8px;
    padding: 8px 14px;
}
QPushButton:hover {
    background: #3b4252;
    border-color: #5e81ac;
}
QPushButton#DangerButton {
    background: #8b1e2d;
    border-color: #b94052;
    color: #fff;
    font-weight: 700;
}
QPushButton#DangerButton:hover {
    background: #a32637;
}
QPushButton:disabled {
    color: #6a7488;
    border-color: #3a4354;
}
QSpinBox, QTableWidget, QPlainTextEdit, QComboBox {
    background: #20262d;
    border: 1px solid #3f4755;
    border-radius: 8px;
}
QHeaderView::section {
    background: #2b313b;
    color: #d8dee9;
    border: none;
    padding: 6px;
}
QProgressBar {
    border: 1px solid #4c566a;
    border-radius: 6px;
    text-align: center;
    background: #252b34;
}
QProgressBar::chunk {
    border-radius: 5px;
    background: #5e81ac;
}
"""


LIGHT_STYLESHEET = """
QWidget {
    background: #f4f6f8;
    color: #1f2933;
    font-family: "Noto Sans", "Cantarell", sans-serif;
    font-size: 13px;
}
QLabel#Title {
    font-size: 24px;
    font-weight: 700;
    color: #102a43;
}
QLabel#Subtitle {
    color: #486581;
}
QFrame#DropZone {
    border: 2px dashed #c73647;
    border-radius: 12px;
    min-height: 120px;
    background: #ffffff;
}
QFrame#DropZone[hover="true"] {
    border: 2px solid #1f8b4c;
    background: #eefbf3;
}
QPushButton {
    background: #ffffff;
    border: 1px solid #9fb3c8;
    border-radius: 8px;
    padding: 8px 14px;
}
QPushButton:hover {
    background: #e9eef5;
}
QPushButton#DangerButton {
    background: #c92a2a;
    border-color: #de4f4f;
    color: #fff;
    font-weight: 700;
}
QSpinBox, QTableWidget, QPlainTextEdit, QComboBox {
    background: #ffffff;
    border: 1px solid #bcccdc;
    border-radius: 8px;
}
QHeaderView::section {
    background: #d9e2ec;
    color: #102a43;
    border: none;
    padding: 6px;
}
QProgressBar {
    border: 1px solid #829ab1;
    border-radius: 6px;
    text-align: center;
    background: #ffffff;
}
QProgressBar::chunk {
    border-radius: 5px;
    background: #3e7cb1;
}
"""


def apply_theme(app: QApplication, theme: str, system_palette: QPalette, system_style: str) -> None:
    if theme == "dark":
        app.setStyle("Fusion")
        app.setStyleSheet(DARK_STYLESHEET)
        return
    if theme == "light":
        app.setStyle("Fusion")
        app.setStyleSheet(LIGHT_STYLESHEET)
        return
    app.setStyle(system_style)
    app.setStyleSheet("")
    app.setPalette(system_palette)
