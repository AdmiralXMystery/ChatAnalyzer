# ui/page_organizer.py
import asyncio
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel
)

from core.folder_processor import process_vk_archive_async
from ui.widgets import (
    PageHeader, Card, LogWidget, PathPicker, RunPanel, ToggleSwitch
)


class OrganizerPage(QWidget):
    def __init__(self, main_window=None):
        super().__init__()
        self.main = main_window

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        root.addWidget(PageHeader(
            "Упорядочивание папок VK",
            "Переименование или копирование папок чатов по именам из index-messages.html"
        ))

        # ============================================================
        # Карточка «Источник»
        # ============================================================
        src_card = Card("Источник")
        self.src_picker = PathPicker(
            "Путь к архиву VK (корень или папка messages)",
            mode="dir"
        )
        src_card.add(self.src_picker)
        root.addWidget(src_card)

        # ============================================================
        # Карточка «Назначение и режим»
        # ============================================================
        dst_card = Card("Назначение и режим")

        # Путь для сохранения — активируется только в режиме копирования
        self.dst_picker = PathPicker(
            "Путь для сохранения (только в режиме копирования)",
            mode="dir"
        )
        self.dst_picker.set_enabled(False)
        dst_card.add(self.dst_picker)

        # === ToggleSwitch вместо чекбокса ===
        # Выкл (по умолчанию) → переименовать на месте
        # Вкл              → копировать в целевую папку
        self.copy_toggle = ToggleSwitch(
            left_label="Переименовать на месте",
            right_label="Копировать",
        )
        self.copy_toggle.setChecked(False)
        self.copy_toggle.setMinimumHeight(34)

        # Центрируем переключатель
        toggle_row = QHBoxLayout()
        toggle_row.addStretch(1)
        toggle_row.addWidget(self.copy_toggle)
        toggle_row.addStretch(1)
        dst_card.add_layout(toggle_row)

        root.addWidget(dst_card)

        # ============================================================
        # Запуск
        # ============================================================
        self.run_panel = RunPanel("🚀   Запустить обработку")
        self.run_panel.btn.clicked.connect(self._start)
        root.addWidget(self.run_panel)

        # ============================================================
        # Лог
        # ============================================================
        log_card = Card("Журнал")
        self.log = LogWidget()
        self.log.setMinimumHeight(220)
        log_card.add_widget(self.log, stretch=1)
        root.addWidget(log_card, 1)

        # ============================================================
        # Сигналы
        # ============================================================
        self.src_picker.path_changed.connect(self._validate)
        self.dst_picker.path_changed.connect(self._validate)
        self.copy_toggle.toggled.connect(self._on_copy_toggled)

        # Начальная валидация
        self._validate()

    # ============================================================
    # Слоты
    # ============================================================
    def _on_copy_toggled(self, checked: bool):
        """
        checked = False → переименовать на месте
        checked = True  → копировать
        """
        self.dst_picker.set_enabled(checked)
        self._validate()

    def _validate(self):
        src = self.src_picker.value()
        ok = bool(src)

        # Если включён режим копирования — путь назначения обязателен
        # и не должен совпадать с источником
        if ok and self.copy_toggle.isChecked():
            dst = self.dst_picker.value()
            ok = bool(dst)
            if ok:
                try:
                    if Path(src).resolve() == Path(dst).resolve():
                        ok = False
                except Exception:
                    pass

        self.run_panel.btn.setEnabled(ok)

    def _start(self):
        self.run_panel.set_running(True)
        self.log.clear()
        asyncio.ensure_future(self._run())

    async def _run(self):
        try:
            await process_vk_archive_async(
                archive_root=self.src_picker.value(),
                target_dir=self.dst_picker.value(),
                copy_mode=self.copy_toggle.isChecked(),
                log_callback=self._log_cb,
            )
        except Exception as e:
            self.log.log(f"💥 Ошибка: {e}")
        finally:
            self.run_panel.set_running(False)

    def _log_cb(self, text: str):
        self.log.log(text)