# nuitka-project: --standalone
# nuitka-project: --enable-plugin=pyside6
# nuitka-project: --enable-plugin=matplotlib
# nuitka-project: --include-package=core
# nuitka-project: --include-package=ui
# nuitka-project: --include-data-dir=templates=templates
# nuitka-project: --windows-console-mode=disable
# nuitka-project: --include-package=pymorphy3_dicts_ru
# nuitka-project: --include-data-dir=pymorphy3_dicts_ru/data=pymorphy3_dicts_ru/data
# nuitka-project: --include-data-dir=resources=resources
# nuitka-project: --include-data-dir=.venv/Lib/site-packages/wordcloud=wordcloud
# nuitka-project: --windows-icon-from-ico=chat_analyzer_icon.ico

import sys
import asyncio
import qasync
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Chat Analyzer")
    app.setStyle("Fusion")

    # Единый шрифт
    font = QFont("Segoe UI", 11)
    app.setFont(font)

    app.setStyleSheet(APP_STYLESHEET)

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow()
    window.showMaximized()

    with loop:
        loop.run_forever()


# ============================================================
# СВЕТЛАЯ ТЕМА
# ============================================================
APP_STYLESHEET = """
/* ---------- База ---------- */
QWidget {
    background-color: #f5f7fa;
    color: #1f2937;
    font-family: 'Segoe UI', 'Inter', 'Helvetica Neue', sans-serif;
    font-size: 11pt;
}
QMainWindow, QDialog { background-color: #f5f7fa; }

/* ---------- Сайдбар ---------- */
QListWidget#Sidebar {
    background-color: #ffffff;
    border: none;
    border-right: 1px solid #e5e7eb;
    outline: none;
    padding: 12px 0;
}
QListWidget#Sidebar::item {
    padding: 11px 20px;
    border-radius: 8px;
    margin: 2px 10px;
    color: #4b5563;
    font-size: 10.5pt;
}
QListWidget#Sidebar::item:hover {
    background-color: #eef2ff;
    color: #1e40af;
}
QListWidget#Sidebar::item:selected {
    background-color: #2563eb;
    color: #ffffff;
    font-weight: 600;
}

/* ---------- Заголовки ---------- */
QLabel#PageTitle {
    font-size: 18pt;
    font-weight: 700;
    color: #111827;
}
QLabel#PageSubtitle {
    font-size: 11pt;
    color: #6b7280;
}
QLabel#CardTitle {
    font-size: 12pt;
    font-weight: 600;
    color: #1f2937;
}
QLabel#Hint {
    font-size: 10pt;
    color: #6b7280;
}

/* ---------- Поля ввода ---------- */
QLineEdit, QPlainTextEdit, QTextEdit {
    background-color: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    padding: 8px 12px;
    color: #1f2937;
    selection-background-color: #bfdbfe;
    selection-color: #1f2937;
}
QLineEdit:hover, QPlainTextEdit:hover, QTextEdit:hover {
    border: 1px solid #9ca3af;
}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {
    border: 1px solid #2563eb;
    background-color: #ffffff;
}
QLineEdit:disabled, QPlainTextEdit:disabled {
    background-color: #f3f4f6;
    color: #9ca3af;
    border: 1px solid #e5e7eb;
}
QLineEdit::placeholder { color: #9ca3af; }

/* ---------- Кнопки ---------- */
QPushButton {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 9px 18px;
    font-weight: 600;
    font-size: 11pt;
}
QPushButton:hover { background-color: #1d4ed8; }
QPushButton:pressed { background-color: #1e40af; }
QPushButton:disabled {
    background-color: #e5e7eb;
    color: #9ca3af;
}

QPushButton#Secondary {
    background-color: #ffffff;
    color: #374151;
    border: 1px solid #d1d5db;
}
QPushButton#Secondary:hover {
    background-color: #f9fafb;
    border-color: #9ca3af;
}
QPushButton#Secondary:pressed {
    background-color: #f3f4f6;
}
QPushButton#Secondary:disabled {
    background-color: #f9fafb;
    color: #d1d5db;
    border-color: #e5e7eb;
}

QPushButton#Ghost {
    background-color: transparent;
    color: #2563eb;
    border: none;
    padding: 6px 10px;
}
QPushButton#Ghost:hover { background-color: #eff6ff; }

/* ---------- Радиокнопки ---------- */
QRadioButton { spacing: 9px; color: #374151; padding: 4px 0; }
QRadioButton::indicator {
    width: 18px; height: 18px;
    border: 1.5px solid #9ca3af;
    border-radius: 9px;
    background-color: #ffffff;
}
QRadioButton::indicator:hover { border-color: #2563eb; }
QRadioButton::indicator:checked {
    border: 5px solid #2563eb;
    background-color: #ffffff;
}

/* ---------- Скроллбары ---------- */
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #cbd5e1;
    border-radius: 5px;
    min-height: 30px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover { background: #94a3b8; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }

QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #cbd5e1;
    border-radius: 5px;
    min-width: 30px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover { background: #94a3b8; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ---------- Прогресс-бар ---------- */
QProgressBar {
    border: none;
    border-radius: 4px;
    background-color: #e5e7eb;
    height: 6px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background-color: #2563eb;
    border-radius: 4px;
}

/* ---------- Карточки ---------- */
QFrame#Card {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
}

/* ---------- Вкладки ---------- */
QTabWidget::pane {
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    background: #ffffff;
    top: -1px;
}
QTabBar::tab {
    background: transparent;
    color: #6b7280;
    padding: 9px 18px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: 500;
}
QTabBar::tab:hover { color: #2563eb; background: #eff6ff; }
QTabBar::tab:selected {
    background: #ffffff;
    color: #2563eb;
    border: 1px solid #e5e7eb;
    border-bottom: 1px solid #ffffff;
    font-weight: 600;
}

/* ---------- Списки ---------- */
QListWidget {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    outline: none;
    padding: 4px;
}
QListWidget::item {
    padding: 8px 10px;
    border-radius: 6px;
    color: #374151;
}
QListWidget::item:hover { background-color: #f3f4f6; }
QListWidget::item:selected {
    background-color: #dbeafe;
    color: #1e40af;
    font-weight: 500;
}

/* ---------- Тултипы ---------- */
QToolTip {
    background-color: #1f2937;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 6px 10px;
}

/* ---------- Разделители ---------- */
QFrame#Divider {
    background-color: #e5e7eb;
    max-height: 1px;
    border: none;
}
"""


if __name__ == "__main__":
    main()