# ui/page_csv.py
import asyncio

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel
)

from core.csv_exporter import process_csv_export_async
from core.csv_exporter_tg_json import process_json_export_async
from ui.widgets import PageHeader, Card, LogWidget, PathPicker, RunPanel, ToggleSwitch


class CsvPage(QWidget):
    def __init__(self, main_window=None):
        super().__init__()
        self.main = main_window

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        root.addWidget(PageHeader(
            "Экспорт сообщений в CSV",
            "Преобразование архивов VK (HTML) или Telegram (JSON) в таблицы CSV"
        ))

        # ---------- Источник ----------
        src_card = Card("Источник данных")

        # === Переключатель источника: VK ←→ Telegram ===
        # Выкл (по умолчанию) = VK, Вкл = Telegram
        self.source_toggle = ToggleSwitch(
            left_label="VK (HTML)",
            right_label="Telegram (JSON)",
        )
        self.source_toggle.setChecked(False)   # VK по умолчанию
        self.source_toggle.setMinimumHeight(34)

        # Центрируем переключатель в карточке
        toggle_row = QHBoxLayout()
        toggle_row.addStretch(1)
        toggle_row.addWidget(self.source_toggle)
        toggle_row.addStretch(1)
        src_card.add_layout(toggle_row)

        self.path_picker = PathPicker("Путь к папке чата / корню архива", mode="dir")
        src_card.add(self.path_picker)

        # Массовая обработка — актуальна только для VK
        self.mass_toggle = ToggleSwitch("Массовая обработка (все папки внутри messages)")
        self.mass_toggle.setChecked(False)
        self.mass_toggle.setMinimumHeight(32)
        src_card.add(self.mass_toggle)

        self.hint = QLabel()
        self.hint.setObjectName("Hint")
        self.hint.setWordWrap(True)
        src_card.add(self.hint)

        root.addWidget(src_card)

        # Сигналы
        self.source_toggle.toggled.connect(self._on_source_changed)
        self.mass_toggle.toggled.connect(lambda _: self._validate())
        self.path_picker.path_changed.connect(self._validate)

        # ---------- Запуск ----------
        self.run_panel = RunPanel("📊   Запустить экспорт в CSV")
        self.run_panel.btn.clicked.connect(self._start)
        root.addWidget(self.run_panel)

        # ---------- Лог ----------
        log_card = Card("Журнал")
        self.log = LogWidget()
        self.log.setMinimumHeight(260)
        log_card.add_widget(self.log, stretch=1)
        root.addWidget(log_card, 1)

        # Инициализация состояния (VK по умолчанию)
        self._on_source_changed(self.source_toggle.isChecked())

    # ============================================================
    # Слоты
    # ============================================================
    def _on_source_changed(self, is_tg: bool):
        """
        is_tg = False → VK
        is_tg = True  → Telegram
        """
        is_vk = not is_tg

        # Массовая обработка доступна только для VK.
        # НЕ прячем — просто дизейблим. Layout стабилен.
        self.mass_toggle.setEnabled(is_vk)
        if not is_vk:
            self.mass_toggle.setChecked(False)

        # Плейсхолдер, фильтр диалога и подсказка
        if is_vk:
            self.path_picker.set_mode("dir", "Путь к папке чата / корню архива")
            self.path_picker.file_filter = ""
            self.hint.setText(
                "VK: папка отдельного чата или корень архива при массовой обработке."
            )
        else:
            self.path_picker.set_mode("file", "Путь к result.json")
            self.path_picker.file_filter = "JSON (*.json);;Все файлы (*.*)"
            self.hint.setText("Telegram: файл result.json.")

        self._validate()

    def _validate(self):
        self.run_panel.btn.setEnabled(bool(self.path_picker.value()))

    def _start(self):
        self.run_panel.set_running(True)
        self.log.clear()
        asyncio.ensure_future(self._run())

    async def _run(self):
        try:
            if self.source_toggle.isChecked():  # True → Telegram
                await process_json_export_async(
                    file_or_folder_path=self.path_picker.value(),
                    log_callback=self._log_cb,  # ← обычная функция, не корутина
                )
            else:
                await process_csv_export_async(
                    folder_path=self.path_picker.value(),
                    mass_mode=self.mass_toggle.isChecked(),
                    log_callback=self._log_cb,
                )
        except Exception as e:
            self.log.log(f"💥 Ошибка: {e}")
        finally:
            self.run_panel.set_running(False)

    def _log_cb(self, text: str):
        """Синхронный колбэк — LogWidget.log() сам эмитит Qt-сигнал
        и безопасно доставляет текст в UI-поток."""
        self.log.log(text)