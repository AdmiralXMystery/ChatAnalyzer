# ui/page_settings.py
import os
import sys
import shutil
import subprocess
import asyncio
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QFrame
)

from ui.widgets import PageHeader, Card, LogWidget


# ============================================================
# Утилиты
# ============================================================
def _fmt_size(num_bytes: int) -> str:
    """Человекочитаемый размер."""
    size = float(num_bytes)
    for unit in ["Б", "КБ", "МБ", "ГБ", "ТБ"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} ПБ"


def _dir_size_and_count(folder: Path) -> tuple[int, int]:
    """Возвращает (общий размер в байтах, количество файлов)."""
    if not folder.exists():
        return 0, 0
    total = 0
    count = 0
    for path in folder.rglob("*"):
        if path.is_file():
            try:
                total += path.stat().st_size
                count += 1
            except OSError:
                pass
    return total, count


# ============================================================
# Карточка «Папка»
# ============================================================
class _FolderCard(Card):
    """Карточка с описанием папки, размером и кнопками действий."""

    def __init__(self, title: str, icon: str, description: str, parent=None):
        super().__init__()
        self._log_cb = None          # задаётся извне через bind_callbacks
        self._on_show = None
        self._on_clear = None

        # --- Заголовок с иконкой ---
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 16pt;")
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            "font-size: 12pt; font-weight: 600; color: #1f2937;"
        )
        header_row.addWidget(icon_lbl)
        header_row.addWidget(title_lbl)
        header_row.addStretch(1)
        self.add_layout(header_row)

        # --- Описание ---
        desc_lbl = QLabel(description)
        desc_lbl.setObjectName("Hint")
        desc_lbl.setWordWrap(True)
        self.add(desc_lbl)

        # --- Размер ---
        size_row = QHBoxLayout()
        size_row.setSpacing(6)
        size_caption = QLabel("Размер:")
        size_caption.setStyleSheet("color: #4b5563;")
        self.size_label = QLabel("—")
        self.size_label.setStyleSheet(
            "color: #1f2937; font-weight: 600; font-size: 10.5pt;"
        )
        size_row.addWidget(size_caption)
        size_row.addWidget(self.size_label)
        size_row.addStretch(1)
        self.add_layout(size_row)

        # --- Кнопки ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.show_btn = QPushButton("📂  Показать в проводнике")
        self.show_btn.setObjectName("Secondary")
        self.show_btn.setMinimumHeight(36)
        self.show_btn.clicked.connect(self._handle_show)

        self.clear_btn = QPushButton("🧹  Очистить папку")
        self.clear_btn.setMinimumHeight(36)
        # Красный вариант
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 9px 18px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #b91c1c; }
            QPushButton:pressed { background-color: #991b1b; }
            QPushButton:disabled {
                background-color: #e5e7eb;
                color: #9ca3af;
            }
        """)
        self.clear_btn.clicked.connect(self._handle_clear)

        btn_row.addWidget(self.show_btn)
        btn_row.addWidget(self.clear_btn)
        btn_row.addStretch(1)
        self.add_layout(btn_row)

    def bind_callbacks(self, on_show, on_clear):
        self._on_show = on_show
        self._on_clear = on_clear

    def set_size_text(self, text: str):
        self.size_label.setText(text)

    def _handle_show(self):
        if self._on_show:
            self._on_show()

    def _handle_clear(self):
        if self._on_clear:
            self._on_clear()


# ============================================================
# Страница
# ============================================================
class CacheManagerPage(QWidget):
    def __init__(self, main_window=None):
        super().__init__()
        self.main = main_window

        # Пути считаем относительно корня проекта
        self.project_root = Path(__file__).resolve().parents[1]
        self.cache_dir = self.project_root / "cache"
        self.csv_dir = self.project_root / "csv_data"

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        root.addWidget(PageHeader(
            "Управление служебными папками",
            "Просмотр размеров и очистка папок с временными и служебными данными."
        ))

        # ============================================================
        # Карточка cache
        # ============================================================
        self.card_cache = _FolderCard(
            title="Папка cache",
            icon="🗂",
            description=(
                "Содержит сгенерированные HTML-отчёты, графики и облака слов "
                "по каждому проанализированному чату."
            ),
        )
        self.card_cache.bind_callbacks(
            on_show=self._show_cache,
            on_clear=self._clear_cache,
        )
        root.addWidget(self.card_cache)

        # ============================================================
        # Карточка csv_data
        # ============================================================
        self.card_csv = _FolderCard(
            title="Папка csv_data",
            icon="📊",
            description=(
                "Содержит CSV-файлы, полученные при экспорте сообщений "
                "из HTML-архива или Telegram JSON."
            ),
        )
        self.card_csv.bind_callbacks(
            on_show=self._show_csv,
            on_clear=self._clear_csv,
        )
        root.addWidget(self.card_csv)

        # ============================================================
        # Кнопка обновления
        # ============================================================
        refresh_btn = QPushButton("🔄  Обновить статистику")
        refresh_btn.setObjectName("Secondary")
        refresh_btn.setMinimumHeight(38)
        refresh_btn.clicked.connect(self.refresh_stats)

        refresh_row = QHBoxLayout()
        refresh_row.addStretch(1)
        refresh_row.addWidget(refresh_btn)
        refresh_row.addStretch(1)
        root.addLayout(refresh_row)

        # ============================================================
        # Лог
        # ============================================================
        log_card = Card("Журнал")
        self.log = LogWidget()
        self.log.setMinimumHeight(180)
        log_card.add_widget(self.log, stretch=1)
        root.addWidget(log_card, 1)

        # Первичное обновление статистики
        self.refresh_stats()

    # ============================================================
    # Статистика
    # ============================================================
    def refresh_stats(self):
        """Считает размеры папок в фоновом потоке, чтобы не подвисало UI."""
        # Сразу показываем «считаем...»
        self.card_cache.set_size_text("подсчёт…")
        self.card_csv.set_size_text("подсчёт…")

        asyncio.ensure_future(self._refresh_stats_async())

    async def _refresh_stats_async(self):
        try:
            cache_res, csv_res = await asyncio.gather(
                asyncio.to_thread(_dir_size_and_count, self.cache_dir),
                asyncio.to_thread(_dir_size_and_count, self.csv_dir),
            )

            cache_size, cache_files = cache_res
            csv_size, csv_files = csv_res

            if self.cache_dir.exists():
                self.card_cache.set_size_text(
                    f"{_fmt_size(cache_size)} · файлов: {cache_files}"
                )
            else:
                self.card_cache.set_size_text("папка отсутствует")

            if self.csv_dir.exists():
                self.card_csv.set_size_text(
                    f"{_fmt_size(csv_size)} · файлов: {csv_files}"
                )
            else:
                self.card_csv.set_size_text("папка отсутствует")

        except Exception as e:
            self.log.log(f"⚠️  Ошибка при подсчёте размеров: {e}\n")

    # ============================================================
    # Публичный хук для MainWindow
    # ============================================================
    def refresh_list(self):
        self.refresh_stats()

    # ============================================================
    # Открытие в проводнике
    # ============================================================
    def _open_in_explorer(self, folder: Path):
        if not folder.exists():
            folder.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(str(folder))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
            self.log.log(f"📂  Открыто в проводнике: {folder}\n")
        except Exception as err:
            self.log.log(f"💥  Ошибка открытия папки: {err}\n")

    def _show_cache(self):
        self._open_in_explorer(self.cache_dir)

    def _show_csv(self):
        self._open_in_explorer(self.csv_dir)

    # ============================================================
    # Очистка папок
    # ============================================================
    def _clear_cache(self):
        self._confirm_clear(self.cache_dir, "cache")

    def _clear_csv(self):
        self._confirm_clear(self.csv_dir, "csv_data")

    def _confirm_clear(self, folder: Path, label: str):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle(f"Очистить папку «{label}»?")
        msg.setText(f"Будут безвозвратно удалены все файлы и подпапки внутри:")
        msg.setInformativeText(str(folder))
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)

        # Переименовываем кнопки на русские
        msg.button(QMessageBox.Yes).setText("Удалить всё")
        msg.button(QMessageBox.Cancel).setText("Отмена")
        msg.setDefaultButton(QMessageBox.Cancel)

        if msg.exec() != QMessageBox.Yes:
            return

        self.log.log(f"🧹  Очистка папки «{label}»...")
        asyncio.ensure_future(self._clear_folder_async(folder, label))

    async def _clear_folder_async(self, folder: Path, label: str):
        try:
            files_del, dirs_del, errors = await asyncio.to_thread(
                self._clear_folder, folder
            )

            if files_del == 0 and dirs_del == 0 and errors == 0:
                self.log.log(
                    f"ℹ️  Папка «{label}» пуста или отсутствует.\n"
                )
            else:
                extra = f", ошибок: {errors}" if errors else ""
                self.log.log(
                    f"✅  Папка «{label}» очищена. "
                    f"Удалено файлов: {files_del}, подпапок: {dirs_del}"
                    f"{extra}.\n"
                )

            # Пересчитываем размеры
            self.refresh_stats()

        except Exception as e:
            self.log.log(f"💥  Ошибка очистки: {e}\n")

    def _clear_folder(self, folder: Path) -> tuple[int, int, int]:
        """Синхронная очистка — вызывается в отдельном потоке."""
        if not folder.exists():
            return 0, 0, 0

        files_deleted = 0
        dirs_deleted = 0
        errors = 0

        for entry in folder.iterdir():
            try:
                if entry.is_dir():
                    shutil.rmtree(entry)
                    dirs_deleted += 1
                else:
                    entry.unlink()
                    files_deleted += 1
            except Exception as err:
                errors += 1
                self.log.log(f"⚠️  Не удалось удалить {entry.name}: {err}\n")

        return files_deleted, dirs_deleted, errors