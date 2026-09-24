# ui/page_viewer.py
import os
import sys
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton,
    QLabel, QLineEdit, QFileDialog
)

from ui.widgets import PageHeader, Card, LogWidget


class ViewerPage(QWidget):
    def __init__(self, main_window=None):
        super().__init__()
        self.main = main_window

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        root.addWidget(PageHeader(
            "Просмотр готовых отчётов",
            "Откройте HTML-отчёт в браузере по умолчанию. "
            "Для сохранения в PDF — Ctrl+P → «Сохранить как PDF»."
        ))

        # ============================================================
        # Карточка: выбор отчёта
        # ============================================================
        select_card = Card("Выбор чата")

        combo_row = QHBoxLayout()
        combo_row.setSpacing(8)

        self.combo = QComboBox()
        self.combo.setMinimumHeight(38)
        self.combo.setMaxVisibleItems(14)
        self.combo.currentIndexChanged.connect(self._on_combo_changed)

        refresh_btn = QPushButton("🔄  Обновить")
        refresh_btn.setObjectName("Secondary")
        refresh_btn.setMinimumHeight(38)
        refresh_btn.setFixedWidth(140)
        refresh_btn.setToolTip("Пересканировать папку cache/ на наличие report.html")
        refresh_btn.clicked.connect(self.refresh_list)

        combo_row.addWidget(self.combo, 1)
        combo_row.addWidget(refresh_btn)
        select_card.add_layout(combo_row)

        # Путь к отчёту
        path_row = QHBoxLayout()
        path_row.setSpacing(8)

        path_label = QLabel("Путь к отчёту:")
        path_label.setFixedWidth(120)
        path_label.setStyleSheet("color: #4b5563;")

        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setMinimumHeight(36)
        self.path_edit.setPlaceholderText("Отчёт не выбран")

        path_row.addWidget(path_label)
        path_row.addWidget(self.path_edit, 1)
        select_card.add_layout(path_row)

        root.addWidget(select_card)

        # ============================================================
        # Кнопка «Открыть в браузере»
        # ============================================================
        self.open_btn = QPushButton("🌐   Открыть в браузере")
        self.open_btn.setMinimumHeight(42)
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self._open_in_browser)

        open_row = QHBoxLayout()
        open_row.addStretch(1)
        open_row.addWidget(self.open_btn)
        open_row.addStretch(1)
        root.addLayout(open_row)

        # ============================================================
        # Лог
        # ============================================================
        log_card = Card("Журнал")
        self.log = LogWidget()
        self.log.setMinimumHeight(200)
        log_card.add_widget(self.log, stretch=1)
        root.addWidget(log_card, 1)

        # Стартовое заполнение
        self.refresh_list()

    # ============================================================
    # Список отчётов
    # ============================================================
    @staticmethod
    def _format_display_name(folder_name: str) -> str:
        if folder_name.startswith("group_"):
            return f"[Групповой]  {folder_name[len('group_'):]}"
        if folder_name.startswith("private_"):
            return f"[Личный]     {folder_name[len('private_'):]}"
        return f"[Другой]     {folder_name}"

    def refresh_list(self):
        """Сканирует cache/ и заполняет combo папками с report.html."""
        previous = self.combo.currentData()

        self.combo.blockSignals(True)
        self.combo.clear()

        cache_dir = Path(".").resolve() / "cache"
        if cache_dir.exists() and cache_dir.is_dir():
            for folder in sorted(cache_dir.iterdir()):
                if not folder.is_dir():
                    continue
                if not (folder / "report.html").exists():
                    continue
                self.combo.addItem(
                    self._format_display_name(folder.name),
                    str(folder)
                )

        # Восстанавливаем выбор
        if previous:
            idx = self.combo.findData(previous)
            if idx >= 0:
                self.combo.setCurrentIndex(idx)

        if self.combo.currentIndex() < 0 and self.combo.count() > 0:
            self.combo.setCurrentIndex(0)

        self.combo.blockSignals(False)
        self._on_combo_changed()

    def _on_combo_changed(self, *_):
        """Обновляет поле пути и доступность кнопки."""
        folder_str = self.combo.currentData()
        report_path = None

        if folder_str:
            candidate = Path(folder_str) / "report.html"
            if candidate.exists():
                report_path = candidate

        self.path_edit.setText(str(report_path) if report_path else "")
        self.open_btn.setEnabled(report_path is not None)

    # ============================================================
    # Открытие в браузере
    # ============================================================
    def _open_in_browser(self):
        folder_str = self.combo.currentData()
        if not folder_str:
            return

        report_path = Path(folder_str) / "report.html"
        if not report_path.exists():
            self.log.log(f"❌  Файл отчёта не найден: {report_path}\n")
            return

        try:
            if sys.platform == "win32":
                os.startfile(str(report_path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(report_path)])
            else:
                subprocess.Popen(["xdg-open", str(report_path)])

            self.log.log(f"🌐  Открыто в браузере: {report_path.name}")
            self.log.log("💡  Для сохранения в PDF: Ctrl+P → «Сохранить как PDF».\n")
        except Exception as err:
            self.log.log(f"💥  Ошибка при открытии: {err}\n")