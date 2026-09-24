# ui/page_analyzer.py
import sys
import io
import asyncio
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QLabel, QSplitter, QScrollArea, QFrame
)

from core.chat_report_generator import ChatReportGenerator
from core.settings_manager import SettingsManager
from ui.widgets import (
    PageHeader, Card, LogWidget, RunPanel, ToggleSwitch, LimitedComboBox
)


class LogRedirector(io.StringIO):
    """Перенаправляет print() в колбэк лога."""
    def __init__(self, log_callback):
        super().__init__()
        self.log_callback = log_callback

    def write(self, s):
        if s.strip():
            self.log_callback(s)
        return len(s)


FEATURES = [
    ("msg_length",       "Динамика длины сообщений", True),
    ("longest_messages", "Самые длинные сообщения", True),
    ("sessions",         "Анализ сессий и инициаторов", True),
    ("reply_speed",      "Скорость ответов участников", True),
    ("activity_charts",  "Графики активности (часы/месяцы)", True),
    ("vocabulary",       "Лексическое богатство и TTR", True),
    ("emoji",            "Статистика эмодзи", True),
    ("linguistics",      "Части речи и грамматика", True),
    ("spelling",         "Орфография и опечатки", True),
    ("profanity",        "Обсценная лексика (18+)", True),
    ("laughter",         "Смех и смайлики", True),
    ("wordclouds",       "Облака слов (Wordcloud)", True),
    ("ai_analysis",      "ИИ-анализ тем (LM Studio)", False),
]


class AnalyzerPage(QWidget):
    def __init__(self, main_window=None):
        super().__init__()
        self.main = main_window

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        root.addWidget(PageHeader(
            "Анализ личной переписки",
            "HTML-отчёт по личной переписке (2 участника)"
        ))

        # ============================================================
        # Двухколоночный сплиттер
        # ============================================================
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)

        # ---------- ЛЕВАЯ КОЛОНКА: настройки ----------
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(14)

        # --- Карточка состава отчёта ---
        feat_card = Card("Состав отчёта")

        self.feature_toggles = {}
        for key, label, default in FEATURES:
            tg = ToggleSwitch(label)
            tg.setChecked(default)
            tg.setMinimumHeight(30)
            self.feature_toggles[key] = tg
            feat_card.add(tg)

        left_layout.addWidget(feat_card)

        # --- Кнопка запуска ---
        self.run_panel = RunPanel("📈   Сгенерировать HTML-отчёт")
        self.run_panel.btn.clicked.connect(self._start)
        left_layout.addWidget(self.run_panel)

        left_layout.addStretch(1)

        left_scroll.setWidget(left_widget)

        # ---------- ПРАВАЯ КОЛОНКА: выбор файла + лог ----------
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(14)

        # --- Карточка выбора CSV ---
        file_card = Card("Выбор CSV-файла")
        file_row = QVBoxLayout()
        file_row.setSpacing(8)

        self.combo = LimitedComboBox(max_popup_height=320, max_visible_items=12)
        self.combo.setMinimumHeight(36)
        self.combo.setMaxVisibleItems(12)
        self.combo.currentIndexChanged.connect(self._validate)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)

        browse_btn = QPushButton("Обзор…")
        browse_btn.setObjectName("Secondary")
        browse_btn.setMinimumHeight(34)
        browse_btn.clicked.connect(self._browse_file)

        refresh_btn = QPushButton("🔄  Обновить")
        refresh_btn.setObjectName("Secondary")
        refresh_btn.setMinimumHeight(34)
        refresh_btn.clicked.connect(self.refresh_list)

        buttons_row.addWidget(browse_btn, 1)
        buttons_row.addWidget(refresh_btn, 1)

        file_row.addWidget(self.combo)
        file_row.addLayout(buttons_row)
        file_card.add_layout(file_row)

        hint = QLabel("По умолчанию список берётся из папки csv_data.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        file_card.add(hint)

        right_layout.addWidget(file_card)

        # --- Карточка журнала ---
        log_card = Card("Журнал")
        self.log = LogWidget()
        self.log.setMinimumHeight(200)
        log_card.add_widget(self.log, stretch=1)

        right_layout.addWidget(log_card, 1)

        # ---------- В сплиттер ----------
        splitter.addWidget(left_scroll)
        splitter.addWidget(right_widget)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([500, 500])

        root.addWidget(splitter, 1)

        self.refresh_list()

    # ============================================================
    # Логика CSV-списка
    # ============================================================
    def refresh_list(self):
        current = self.combo.currentData()
        self.combo.blockSignals(True)
        self.combo.clear()

        csv_dir = Path(".").resolve() / "csv_data"
        if csv_dir.exists() and csv_dir.is_dir():
            for file in sorted(csv_dir.glob("*.csv")):
                self.combo.addItem(file.name, str(file))

        if current:
            idx = self.combo.findData(current)
            if idx >= 0:
                self.combo.setCurrentIndex(idx)

        if self.combo.currentIndex() < 0 and self.combo.count() > 0:
            self.combo.setCurrentIndex(0)

        self.combo.blockSignals(False)
        self._validate()

    def _validate(self, *_):
        self.run_panel.btn.setEnabled(bool(self.combo.currentData()))

    def _browse_file(self):
        initial_dir = str(Path(".").resolve() / "csv_data")
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите CSV-файл", initial_dir,
            "CSV-файлы (*.csv);;Все файлы (*.*)"
        )
        if not path:
            return
        idx = self.combo.findData(path)
        if idx < 0:
            self.combo.addItem(Path(path).name, path)
            idx = self.combo.count() - 1
        self.combo.setCurrentIndex(idx)
        self._validate()

    # ============================================================
    # Запуск
    # ============================================================
    def _start(self):
        csv_path_str = self.combo.currentData()
        if not csv_path_str:
            return
        self.run_panel.set_running(True)
        self.log.clear()
        asyncio.ensure_future(self._run(csv_path_str))

    async def _run(self, csv_path_str: str):
        try:
            csv_path = Path(csv_path_str).resolve()
            chat_name = csv_path.stem
            cache_dir = Path(".").resolve() / "cache" / f"private_{chat_name}"
            cache_dir.mkdir(parents=True, exist_ok=True)

            self.log.log(f"🚀 Изолированная папка кэша личного чата:")
            self.log.log(f"🔹 {cache_dir}\n")

            enabled_features = {
                key: tg.isChecked() for key, tg in self.feature_toggles.items()
            }

            await asyncio.to_thread(
                self._run_pipeline, csv_path, cache_dir, enabled_features
            )

        except Exception as e:
            self.log.log(f"💥 Ошибка: {e}\n")
        finally:
            self.run_panel.set_running(False)

    def _run_pipeline(self, csv_path: Path, cache_dir: Path, enabled_features: dict):
        old_stdout = sys.stdout
        sys.stdout = LogRedirector(self.log.log)
        try:
            generator = ChatReportGenerator(
                csv_path=str(csv_path),
                output_dir=str(cache_dir),
                settings_manager=SettingsManager(),
            )
            generator.run(enabled_features=enabled_features)
        except Exception as pipeline_err:
            self.log.log(f"💥 Ошибка внутри пайплайна анализа: {pipeline_err}\n")
        finally:
            sys.stdout = old_stdout