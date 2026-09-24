# ui/page_settings_dict.py
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QPushButton,
    QLabel, QFrame, QSplitter
)
from PySide6.QtGui import QFont

from core.settings_manager import SettingsManager
from ui.widgets import PageHeader


def _words_to_text(words) -> str:
    return "\n".join(sorted(words))


def _text_to_words(text: str) -> set:
    return {w.strip().lower() for w in text.splitlines() if w.strip()}


class _WordColumn(QFrame):
    """Колонка со словарём: заголовок + подсказка + текстовое поле."""

    def __init__(self, title: str, hint: str, initial_text: str, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 12pt; font-weight: 600; color: #1f2937;")
        layout.addWidget(title_lbl)

        hint_lbl = QLabel(hint)
        hint_lbl.setObjectName("Hint")
        hint_lbl.setWordWrap(True)
        layout.addWidget(hint_lbl)

        self.editor = QPlainTextEdit()
        self.editor.setPlainText(initial_text)
        self.editor.setFont(QFont("Consolas", 10))

        # === ФИКС: не получать фокус автоматически ===
        # Редактирование включится только после клика пользователя.
        self.editor.setFocusPolicy(Qt.ClickFocus)

        self.editor.setStyleSheet("""
            QPlainTextEdit {
                background-color: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 8px 10px;
                color: #1f2937;
                selection-background-color: #bfdbfe;
            }
            QPlainTextEdit:focus { border: 1px solid #2563eb; }
        """)
        layout.addWidget(self.editor, 1)

    def get_words(self) -> set:
        return _text_to_words(self.editor.toPlainText())

    def set_words(self, words):
        self.editor.setPlainText(_words_to_text(words))


class SettingsDictPage(QWidget):
    def __init__(self, main_window=None):
        super().__init__()
        self.main = main_window
        self.manager = SettingsManager()

        # === ФИКС: страница может получать фокус сама ===
        # Это не даёт Qt «проваливать» фокус в первый QPlainTextEdit.
        self.setFocusPolicy(Qt.StrongFocus)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        root.addWidget(PageHeader(
            "Настройки словарей анализатора",
            "Словари, используемые при анализе чата. "
            "Каждое слово — на отдельной строке. "
            "Изменения применятся при следующей генерации отчёта."
        ))

        # ============================================================
        # Три колонки в QSplitter
        # ============================================================
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)

        self.col_stop = _WordColumn(
            "🚫  Стоп-слова",
            "Исключаются из топа слов, TTR и облаков слов.",
            _words_to_text(self.manager.data["stop_words"])
        )
        self.col_whitelist = _WordColumn(
            "✅  Белый список",
            "Слова, которые не считаются ошибкой (сленг, сокращения).",
            _words_to_text(self.manager.data["error_whitelist"])
        )
        self.col_profanity = _WordColumn(
            "⛔  Чёрный список (мат, оскорбления, 18+)",
            "Дополнение к поиску по регулярному выражению.",
            _words_to_text(self.manager.data["profanity_blacklist"])
        )

        splitter.addWidget(self.col_stop)
        splitter.addWidget(self.col_whitelist)
        splitter.addWidget(self.col_profanity)
        splitter.setSizes([340, 340, 340])

        root.addWidget(splitter, 1)

        # ============================================================
        # Кнопки + статус
        # ============================================================
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(10)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #16a34a; font-size: 10pt;")
        buttons_row.addWidget(self.status_label, 1)

        reset_btn = QPushButton("↩  Сбросить к дефолту")
        reset_btn.setObjectName("Secondary")
        reset_btn.setMinimumHeight(38)
        reset_btn.clicked.connect(self._reset)

        save_btn = QPushButton("💾  Сохранить настройки")
        save_btn.setMinimumHeight(38)
        save_btn.clicked.connect(self._save)

        buttons_row.addWidget(reset_btn)
        buttons_row.addWidget(save_btn)

        root.addLayout(buttons_row)

    # ============================================================
    # ФИКС: сбрасываем фокус при каждом показе страницы
    # ============================================================
    def showEvent(self, event):
        super().showEvent(event)
        # Откладываем сброс фокуса до момента, когда виджет уже отрисован.
        # setFocus() вызываем через QTimer, чтобы Qt не назначил фокус
        # первому QPlainTextEdit сразу после showEvent.
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._reset_focus)

    def _reset_focus(self):
        # Ставим фокус на саму страницу, а не на первое текстовое поле.
        self.setFocus(Qt.OtherFocusReason)

    # ============================================================
    # Слоты
    # ============================================================
    def _save(self):
        self.manager.set_stop_words(self.col_stop.get_words())
        self.manager.set_error_whitelist(self.col_whitelist.get_words())
        self.manager.set_profanity_blacklist(self.col_profanity.get_words())
        self.manager.save()

        self.status_label.setStyleSheet("color: #16a34a; font-size: 10pt;")
        self.status_label.setText(
            f"✅  Настройки сохранены в {self.manager.settings_path.name}"
        )

    def _reset(self):
        self.manager.reset_to_defaults()

        self.col_stop.set_words(self.manager.data["stop_words"])
        self.col_whitelist.set_words(self.manager.data["error_whitelist"])
        self.col_profanity.set_words(self.manager.data["profanity_blacklist"])

        self.status_label.setStyleSheet("color: #ea580c; font-size: 10pt;")
        self.status_label.setText("↩  Настройки сброшены к значениям по умолчанию")