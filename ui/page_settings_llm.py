# ui/page_settings_llm.py
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QPushButton,
    QLabel, QFrame, QSplitter
)
from PySide6.QtGui import QFont

from core.settings_manager import SettingsManager
from ui.widgets import PageHeader


def _lines_to_text(items) -> str:
    return "\n".join(items)


def _text_to_lines(text: str) -> list:
    return [line.strip() for line in text.splitlines() if line.strip()]


class _EditorColumn(QFrame):
    """Колонка с редактором: заголовок + подсказка + текстовое поле."""

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

    def get_text(self) -> str:
        return self.editor.toPlainText()

    def get_lines(self) -> list:
        return _text_to_lines(self.editor.toPlainText())

    def set_text(self, text: str):
        self.editor.setPlainText(text)


class SettingsLlmPage(QWidget):
    """Страница редактирования промпта и списков для LLM-анализа."""

    def __init__(self, main_window=None):
        super().__init__()
        self.main = main_window
        self.manager = SettingsManager()

        self.setFocusPolicy(Qt.StrongFocus)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        root.addWidget(PageHeader(
            "Настройки ИИ-анализа (LM Studio)",
            "Системный промпт и списки тем/сентиментов для разметки диалогов. "
            "Изменения применятся при следующей генерации отчёта."
        ))

        # ============================================================
        # Сплиттер: слева — системный промпт, справа — темы/сентименты
        # ============================================================
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)

        # --- Левая колонка: системный промпт ---
        self.col_prompt = _EditorColumn(
            "🧠  Системный промпт",
            "Инструкция для модели. Опишите правила разметки, "
            "требования к полю 'reason' и логику выбора темы/сентимента.",
            self.manager.llm_system_prompt
        )

        # --- Правая колонка: темы + сентименты (вертикально) ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(14)

        self.col_topics = _EditorColumn(
            "🏷  Темы (по одной на строке)",
            "Список допустимых тем. Модель обязана выбрать одну из них "
            "(enum в JSON-схеме).",
            _lines_to_text(self.manager.llm_topics)
        )

        self.col_sentiments = _EditorColumn(
            "🎭  Сентименты / характеры (по одной на строке)",
            "Список допустимых эмоциональных окрасок диалога.",
            _lines_to_text(self.manager.llm_sentiments)
        )

        right_layout.addWidget(self.col_topics, 1)
        right_layout.addWidget(self.col_sentiments, 1)

        splitter.addWidget(self.col_prompt)
        splitter.addWidget(right_widget)
        splitter.setSizes([500, 500])

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
    # Сброс фокуса при показе страницы (как в SettingsDictPage)
    # ============================================================
    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._reset_focus)

    def _reset_focus(self):
        self.setFocus(Qt.OtherFocusReason)

    # ============================================================
    # Слоты
    # ============================================================
    def _save(self):
        self.manager.set_llm_system_prompt(self.col_prompt.get_text())
        self.manager.set_llm_topics(self.col_topics.get_lines())
        self.manager.set_llm_sentiments(self.col_sentiments.get_lines())
        self.manager.save()

        self.status_label.setStyleSheet("color: #16a34a; font-size: 10pt;")
        self.status_label.setText(
            f"✅  Настройки ИИ сохранены в {self.manager.settings_path.name}"
        )

    def _reset(self):
        self.manager.reset_to_defaults()

        self.col_prompt.set_text(self.manager.llm_system_prompt)
        self.col_topics.editor.setPlainText(_lines_to_text(self.manager.llm_topics))
        self.col_sentiments.editor.setPlainText(_lines_to_text(self.manager.llm_sentiments))

        self.status_label.setStyleSheet("color: #ea580c; font-size: 10pt;")
        self.status_label.setText("↩  Настройки ИИ сброшены к значениям по умолчанию")