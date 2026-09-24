# ui/main_window.py
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QListWidget, QListWidgetItem,
    QStackedWidget, QFrame
)

from ui.page_organizer import OrganizerPage
from ui.page_csv import CsvPage
from ui.page_analyzer import AnalyzerPage
from ui.page_group_analyzer import GroupAnalyzerPage
from ui.page_settings_dict import SettingsDictPage
from ui.page_viewer import ViewerPage
from ui.page_settings import CacheManagerPage
from ui.page_settings_llm import SettingsLlmPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chat Analyzer")
        self.setMinimumSize(800, 600)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ---------- Сайдбар ----------
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(300)
        self.sidebar.setFocusPolicy(Qt.NoFocus)
        self.sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # ---------- Стек ----------
        self.stack = QStackedWidget()

        self.pages = {
            "organizer": OrganizerPage(self),
            "csv":       CsvPage(self),
            "analyzer":  AnalyzerPage(self),
            "group":     GroupAnalyzerPage(self),
            "dicts":     SettingsDictPage(self),
            "llm":       SettingsLlmPage(self),
            "viewer":    ViewerPage(self),
            "cache":     CacheManagerPage(self),
        }
        for page in self.pages.values():
            self.stack.addWidget(page)

        menu_items = [
            ("organizer", "🗂   Упорядочить папки"),
            ("csv",       "📊   Экспорт в CSV"),
            ("analyzer",  "📈   Анализ личных чатов"),
            ("group",     "👥   Анализ групповых чатов"),
            ("dicts",     "📚   Настройки словарей"),
            ("llm",       "🧠   Настройки ИИ-анализа"),
            ("viewer",    "📁   Просмотр отчётов"),
            ("cache",     "⚙️   Настройки"),
        ]
        for key, title in menu_items:
            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, key)
            item.setSizeHint(QSize(0, 46))
            self.sidebar.addItem(item)

        self.sidebar.currentRowChanged.connect(self._on_nav_changed)
        self.sidebar.setCurrentRow(0)

        # Разделитель
        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setStyleSheet("background-color: #e5e7eb; max-width: 1px; border: none;")

        layout.addWidget(self.sidebar)
        layout.addWidget(divider)
        layout.addWidget(self.stack, 1)

    def _on_nav_changed(self, index: int):
        if index < 0:
            return
        item = self.sidebar.item(index)
        key = item.data(Qt.UserRole)
        page = self.pages[key]
        self.stack.setCurrentWidget(page)

        if hasattr(page, "refresh_list"):
            try:
                page.refresh_list()
            except Exception as e:
                print(f"[refresh_list] {key}: {e}")