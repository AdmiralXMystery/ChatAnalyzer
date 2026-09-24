# ui/widgets.py
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPlainTextEdit,
    QProgressBar, QPushButton, QFileDialog, QLineEdit, QFrame,
    QGraphicsDropShadowEffect, QSizePolicy
)
from PySide6.QtGui import QFont, QColor
from PySide6.QtCore import Property, QPropertyAnimation, QEasingCurve, QSize, QRectF
from PySide6.QtGui import QPainter, QColor, QBrush, QPen
from PySide6.QtWidgets import QAbstractButton

# ============================================================
# ЛОГ
# ============================================================
class LogWidget(QPlainTextEdit):
    append_signal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Consolas", 10))
        self.setMaximumBlockCount(5000)
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #f9fafb;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 10px 12px;
                color: #1f2937;
                font-family: 'Consolas', 'Menlo', monospace;
                font-size: 9.5pt;
            }
        """)
        self.append_signal.connect(self._do_append)

    def log(self, text: str):
        self.append_signal.emit(text.rstrip("\n"))

    def _do_append(self, text: str):
        self.appendPlainText(text)
        sb = self.verticalScrollBar()
        sb.setValue(sb.maximum())


# ============================================================
# ВЫБОР ПУТИ
# ============================================================
class PathPicker(QWidget):
    path_changed = Signal(str)

    def __init__(self, placeholder: str = "Путь", mode: str = "dir", parent=None):
        super().__init__(parent)
        self.mode = mode
        self.file_filter = ""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.setMinimumHeight(38)

        self.btn = QPushButton("Обзор…")
        self.btn.setObjectName("Secondary")
        self.btn.setFixedWidth(110)
        self.btn.setMinimumHeight(38)
        self.btn.clicked.connect(self._pick)

        self.edit.textChanged.connect(self.path_changed.emit)
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.btn)

    def _pick(self):
        if self.mode == "dir":
            path = QFileDialog.getExistingDirectory(self, "Выберите папку")
        elif self.mode == "file":
            path, _ = QFileDialog.getOpenFileName(
                self, "Выберите файл", "", self.file_filter or "Все файлы (*.*)"
            )
        else:
            path, _ = QFileDialog.getSaveFileName(
                self, "Сохранить как", "", self.file_filter or "Все файлы (*.*)"
            )
        if path:
            self.edit.setText(path)

    def value(self) -> str:
        return self.edit.text().strip()

    def set_value(self, v: str):
        self.edit.setText(v)

    def set_enabled(self, flag: bool):
        self.edit.setEnabled(flag)
        self.btn.setEnabled(flag)

    def set_mode(self, mode: str, placeholder: str = None):
        self.mode = mode
        if placeholder is not None:
            self.edit.setPlaceholderText(placeholder)


# ============================================================
# КАРТОЧКА С ТЕНЬЮ
# ============================================================
class Card(QFrame):
    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")

        # Тень
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(15, 23, 42, 22))
        self.setGraphicsEffect(shadow)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 18, 20, 18)
        self._layout.setSpacing(8)

        if title:
            lbl = QLabel(title)
            lbl.setObjectName("CardTitle")
            self._layout.addWidget(lbl)

    def add(self, w):
        self._layout.addWidget(w)
        return w

    def add_layout(self, l):
        self._layout.addLayout(l)

    def add_widget(self, w, stretch: int = 0):
        self._layout.addWidget(w, stretch)
        return w


# ============================================================
# ЗАГОЛОВОК СТРАНИЦЫ
# ============================================================
class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 4)
        v.setSpacing(4)

        t = QLabel(title)
        t.setObjectName("PageTitle")
        v.addWidget(t)

        if subtitle:
            s = QLabel(subtitle)
            s.setObjectName("PageSubtitle")
            s.setWordWrap(True)
            v.addWidget(s)


# ============================================================
# ПАНЕЛЬ ЗАПУСКА
# ============================================================
class RunPanel(QWidget):
    def __init__(self, button_text: str, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        self.btn = QPushButton(button_text)
        self.btn.setMinimumHeight(42)
        self.btn.setEnabled(False)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        self.progress.setFixedHeight(6)

        v.addWidget(self.btn)
        v.addWidget(self.progress)

    def set_running(self, running: bool):
        self.btn.setEnabled(not running)
        self.progress.setVisible(running)

class ToggleSwitch(QAbstractButton):
    """
    Кастомный toggle-переключатель.

    Два режима отображения:
    1. Обычный (по умолчанию): [track] Текст  — текст справа от трека.
    2. С подписями по бокам: Left [track] Right — обе подписи видны,
       активная выделяется жирным/тёмным, неактивная — серым.

    Совместим с QCheckBox: isChecked(), setChecked(), toggled, clicked, setEnabled().
    """

    def __init__(self, text: str = "",
                 left_label: str = "",
                 right_label: str = "",
                 parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)

        self._text = text
        self._left_label = left_label
        self._right_label = right_label
        self._side_labels = bool(left_label or right_label)

        # Геометрия
        self._track_w = 46
        self._track_h = 24
        self._thumb_margin = 3
        self._thumb_d = self._track_h - 2 * self._thumb_margin  # 18
        self._side_spacing = 10  # отступ между подписью и треком

        # Позиция бегунка (0.0 — влево/выкл, 1.0 — вправо/вкл)
        self._position = 0.0

        # Анимация
        self._anim = QPropertyAnimation(self, b"position", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)

        self.setMinimumHeight(self._track_h + 8)
        self.toggled.connect(self._animate)

    # ---------- Свойство для анимации ----------
    def _get_position(self) -> float:
        return self._position

    def _set_position(self, value: float):
        self._position = max(0.0, min(1.0, float(value)))
        self.update()

    position = Property(float, _get_position, _set_position)

    # ---------- Анимация ----------
    def _animate(self, checked: bool):
        self._anim.stop()
        self._anim.setStartValue(self._position)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    # ---------- Размеры ----------
    def _measure_text(self, txt: str, bold: bool = False) -> int:
        if not txt:
            return 0
        f = QFont(self.font())
        f.setBold(bold)
        from PySide6.QtGui import QFontMetrics
        return QFontMetrics(f).horizontalAdvance(txt)

    def sizeHint(self) -> QSize:
        if self._side_labels:
            # Left [track] Right
            w_left = self._measure_text(self._left_label, bold=True)
            w_right = self._measure_text(self._right_label, bold=True)
            total_w = (
                w_left + self._side_spacing
                + self._track_w + self._side_spacing
                + w_right
            )
            return QSize(total_w + 4, self._track_h + 8)
        else:
            # [track] Text
            text_w = self._measure_text(self._text)
            spacing = self._side_spacing if self._text else 0
            return QSize(self._track_w + spacing + text_w + 4, self._track_h + 8)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    # ---------- Отрисовка ----------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        enabled = self.isEnabled()
        checked = self.isChecked()

        # --- Цвета ---
        if not enabled:
            track_on = QColor("#cbd5e1")
            track_off = QColor("#e5e7eb")
            thumb_color = QColor("#f3f4f6")
            text_color = QColor("#c7cbd1")
            active_text_color = QColor("#9ca3af")
        else:
            track_on = QColor("#2563eb")
            track_off = QColor("#d1d5db")
            thumb_color = QColor("#ffffff")
            text_color = QColor("#9ca3af")
            active_text_color = QColor("#1f2937")

        # --- Позиция трека по горизонтали ---
        if self._side_labels:
            w_left = self._measure_text(self._left_label, bold=True)
            track_x = w_left + self._side_spacing
        else:
            track_x = 0

        track_y = (self.height() - self._track_h) / 2.0
        track_rect = QRectF(track_x, track_y, self._track_w, self._track_h)

        # --- Трек (интерполяция цвета) ---
        t = self._position
        r = int(track_off.red()   + (track_on.red()   - track_off.red())   * t)
        g = int(track_off.green() + (track_on.green() - track_off.green()) * t)
        b = int(track_off.blue()  + (track_on.blue()  - track_off.blue())  * t)
        track_color = QColor(r, g, b)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(track_color))
        painter.drawRoundedRect(track_rect, self._track_h / 2.0, self._track_h / 2.0)

        # --- Бегунок ---
        x_min = track_x + self._thumb_margin
        x_max = track_x + self._track_w - self._thumb_d - self._thumb_margin
        x = x_min + (x_max - x_min) * self._position
        thumb_rect = QRectF(x, track_y + self._thumb_margin,
                            self._thumb_d, self._thumb_d)

        # Тень бегунка
        painter.setBrush(QBrush(QColor(0, 0, 0, 30)))
        painter.drawEllipse(thumb_rect.translated(0, 1))

        painter.setBrush(QBrush(thumb_color))
        painter.drawEllipse(thumb_rect)

        # --- Подписи ---
        if self._side_labels:
            # Слева
            left_color = active_text_color if not checked else text_color
            f_left = QFont(self.font())
            f_left.setBold(not checked)
            painter.setFont(f_left)
            painter.setPen(QPen(left_color))
            left_rect = QRectF(0, 0, w_left, self.height())
            painter.drawText(left_rect, Qt.AlignVCenter | Qt.AlignRight, self._left_label)

            # Справа
            right_x = track_x + self._track_w + self._side_spacing
            right_color = active_text_color if checked else text_color
            f_right = QFont(self.font())
            f_right.setBold(checked)
            painter.setFont(f_right)
            painter.setPen(QPen(right_color))
            right_rect = QRectF(right_x, 0, self.width() - right_x, self.height())
            painter.drawText(right_rect, Qt.AlignVCenter | Qt.AlignLeft, self._right_label)
        else:
            if self._text:
                painter.setFont(self.font())
                painter.setPen(QPen(text_color if enabled else active_text_color))
                text_x = self._track_w + self._side_spacing
                text_rect = QRectF(text_x, 0, self.width() - text_x, self.height())
                painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self._text)

        painter.end()

    # ---------- API ----------
    def setText(self, text: str):
        self._text = text
        self.updateGeometry()
        self.update()

    def text(self) -> str:
        return self._text



# ui/widgets.py (добавить в конец)

from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QComboBox, QListView


class LimitedComboBox(QComboBox):
    """
    QComboBox с двумя доработками:
    1. Максимальная высота popup'а в пикселях (max_popup_height).
    2. Popup всегда открывается СТРОГО ПОД combo, не «прыгает» вверх.
    3. Высота popup'а рассчитывается с запасом, чтобы последняя строка
       не обрезалась.
    """

    # Запас на padding контейнера popup'а (сверху+снизу)
    _EXTRA_PADDING = 10

    def __init__(self, parent=None, max_popup_height: int = 340,
                 max_visible_items: int = 12):
        super().__init__(parent)
        self._max_popup_height = max_popup_height
        self.setMaxVisibleItems(max_visible_items)

    def setMaxPopupHeight(self, h: int):
        self._max_popup_height = h

    def _row_height(self) -> int:
        """
        Возвращает МАКСИМАЛЬНУЮ высоту строки среди всех элементов.
        sizeHintForRow(0) может быть меньше реальной (если первый элемент
        короткий) — из-за этого последняя строка режется.
        """
        view = self.view()
        if view is None:
            return 24

        count = self.count()
        if count == 0:
            return 24

        # Берём max по всем элементам (для combo это быстро — их десятки)
        max_h = 0
        for i in range(count):
            h = view.sizeHintForRow(i)
            if h > max_h:
                max_h = h

        return max_h if max_h > 0 else 24

    def showPopup(self):
        super().showPopup()

        view = self.view()
        if view is None:
            return

        count = self.count()
        if count == 0:
            return

        row_h = self._row_height()
        frame = view.frameWidth() * 2
        h_scroll_h = view.horizontalScrollBar().sizeHint().height() \
            if view.horizontalScrollBarPolicy() != Qt.ScrollBarAlwaysOff \
            else 0

        visible = min(count, self.maxVisibleItems())

        # Высота списка: строки + рамка + (опционально) гор. скроллбар + запас
        content_h = (
            row_h * visible
            + frame
            + h_scroll_h
            + self._EXTRA_PADDING
        )

        target_h = min(content_h, self._max_popup_height)

        container = view.parentWidget()
        if container is None:
            return

        # Ограничиваем высоту контейнера и view
        container.setFixedHeight(target_h)
        # view занимает всё, кроме рамки контейнера
        view.setFixedHeight(target_h - frame)

        # Позиционируем popup строго под combo
        bottom_left = self.mapToGlobal(QPoint(0, self.height()))
        container.move(bottom_left)

        # Прижимаем текущий элемент к верху списка
        current_index = self.currentIndex()
        if current_index >= 0:
            view.scrollTo(
                self.model().index(current_index, 0),
                QListView.PositionAtTop
            )