"""macOS-styled widgets drawn with QPainter."""

from PySide6.QtCore import (Property, QEasingCurve, QPointF, QPropertyAnimation,
                            QRectF, QSize, Qt, QTimer, Signal)
from PySide6.QtGui import (QBrush, QColor, QFont, QIcon, QPainter, QPainterPath,
                           QPen, QPixmap)
from PySide6.QtWidgets import (QAbstractButton, QComboBox, QFrame, QHBoxLayout,
                               QLabel, QVBoxLayout, QWidget)

LIGHT = {
    "window": "#FFFFFF", "sidebar": "#ECECEE", "card": "#FFFFFF", "cardBorder": "#E1E1E5",
    "text": "#1D1D1F", "secondary": "#6E6E73", "separator": "#E4E4E8",
    "accent": "#007AFF", "control": "#FFFFFF", "controlBorder": "#CDCDD2",
    "hover": "rgba(0,0,0,0.06)", "pressed": "rgba(0,0,0,0.11)",
    "stage": "#F5F5F7", "live": "#141416", "selection": "#007AFF",
}
DARK = {
    "window": "#1E1E20", "sidebar": "#28282B", "card": "#323235", "cardBorder": "#3B3B3F",
    "text": "#F5F5F7", "secondary": "#98989D", "separator": "#3A3A3D",
    "accent": "#0A84FF", "control": "#3A3A3D", "controlBorder": "#4A4A4E",
    "hover": "rgba(255,255,255,0.08)", "pressed": "rgba(255,255,255,0.14)",
    "stage": "#1E1E20", "live": "#0C0C0D", "selection": "#0A84FF",
}

UI_FONT = "Segoe UI Variable Text"


def stylesheet(t):
    return f"""
    * {{ font-family: "{UI_FONT}", "Segoe UI"; font-size: 13px; color: {t['text']}; }}
    QToolTip {{ background: {t['card']}; color: {t['text']}; border: 1px solid {t['cardBorder']};
               border-radius: 6px; padding: 4px 8px; }}
    #root {{ background: {t['window']}; }}
    #sidebar {{ background: {t['sidebar']}; border-right: 1px solid {t['separator']}; }}
    #content, #toolbar {{ background: {t['window']}; }}
    #toolbar {{ border-bottom: 1px solid {t['separator']}; }}
    #stage {{ background: {t['stage']}; }}
    #title {{ font-size: 15px; font-weight: 600; }}
    #subtitle, .secondary {{ color: {t['secondary']}; font-size: 12px; }}
    #sectionHeader {{ color: {t['secondary']}; font-size: 11px; font-weight: 600;
                     padding-left: 6px; }}
    #card {{ background: {t['card']}; border: 1px solid {t['cardBorder']}; border-radius: 10px; }}
    #rowSep {{ background: {t['separator']}; max-height: 1px; min-height: 1px; border: none; }}
    #rowLabel {{ background: transparent; }}
    #rowValue {{ color: {t['secondary']}; background: transparent; }}
    #counter {{ color: {t['secondary']}; font-size: 12px; }}
    #banner {{ background: {t['card']}; border: 1px solid {t['cardBorder']}; border-radius: 12px; }}
    #bannerTitle {{ font-size: 15px; font-weight: 600; }}

    QComboBox {{ background: {t['control']}; border: 1px solid {t['controlBorder']};
                border-radius: 6px; padding: 3px 26px 3px 9px; min-height: 20px; min-width: 96px; }}
    QComboBox:disabled {{ color: {t['secondary']}; }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox::down-arrow {{ image: none; width: 0; height: 0; }}
    QComboBox QAbstractItemView {{ background: {t['card']}; border: 1px solid {t['cardBorder']};
                border-radius: 8px; padding: 4px; outline: 0;
                selection-background-color: {t['selection']}; selection-color: white; }}
    QComboBox QAbstractItemView::item {{ min-height: 24px; padding: 0 8px; border-radius: 5px; }}

    QLineEdit {{ background: {t['control']}; border: 1px solid {t['controlBorder']};
                border-radius: 6px; padding: 4px 8px; selection-background-color: {t['accent']}; }}
    QLineEdit:focus {{ border: 2px solid {t['accent']}; padding: 3px 7px; }}

    QPushButton {{ background: {t['control']}; border: 1px solid {t['controlBorder']};
                  border-radius: 6px; padding: 4px 12px; min-height: 18px; }}
    QPushButton:hover {{ background: {t['hover']}; }}
    QPushButton:pressed {{ background: {t['pressed']}; }}
    QPushButton#primary {{ background: {t['accent']}; color: white; border: none; }}
    QPushButton#primary:hover {{ background: {t['accent']}; }}

    QToolButton {{ background: transparent; border: none; border-radius: 6px; padding: 4px 8px; }}
    QToolButton:hover {{ background: {t['hover']}; }}
    QToolButton:pressed, QToolButton:checked {{ background: {t['pressed']}; }}
    QToolButton:disabled {{ color: {t['secondary']}; }}

    QListWidget {{ background: transparent; border: none; outline: 0; }}
    QListWidget::item {{ border-radius: 8px; padding: 3px; border: 2px solid transparent; }}
    QListWidget::item:selected {{ border: 2px solid {t['accent']}; background: transparent; }}
    QListWidget::item:hover {{ background: {t['hover']}; }}

    QScrollArea {{ background: transparent; border: none; }}
    QScrollBar:horizontal, QScrollBar:vertical {{ background: transparent; height: 8px; width: 8px; margin: 0; }}
    QScrollBar::handle {{ background: {t['controlBorder']}; border-radius: 4px; min-width: 30px; min-height: 30px; }}
    QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
        background: none; width: 0; height: 0; }}
    """


# ------------------------------------------------------------------ icons
def make_icon(kind, color, size=18):
    """Simple line icons in the spirit of SF Symbols."""
    scale = 3
    pm = QPixmap(size * scale, size * scale)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(scale * size / 18.0, scale * size / 18.0)
    pen = QPen(QColor(color), 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    if kind == "camera":
        path = QPainterPath()
        path.addRoundedRect(QRectF(2, 5, 14, 10), 2.5, 2.5)
        p.drawPath(path)
        p.drawLine(QPointF(6.5, 5), QPointF(7.5, 3))
        p.drawLine(QPointF(7.5, 3), QPointF(10.5, 3))
        p.drawLine(QPointF(10.5, 3), QPointF(11.5, 5))
        p.drawEllipse(QPointF(9, 10), 2.8, 2.8)
    elif kind == "folder":
        path = QPainterPath()
        path.moveTo(2, 5)
        path.lineTo(2, 14)
        path.quadTo(2, 15, 3, 15)
        path.lineTo(15, 15)
        path.quadTo(16, 15, 16, 14)
        path.lineTo(16, 6.5)
        path.quadTo(16, 5.5, 15, 5.5)
        path.lineTo(9, 5.5)
        path.lineTo(7.5, 3.5)
        path.lineTo(3, 3.5)
        path.quadTo(2, 3.5, 2, 5)
        p.drawPath(path)
    elif kind == "eye":
        path = QPainterPath()
        path.moveTo(1.5, 9)
        path.quadTo(9, 1.5, 16.5, 9)
        path.quadTo(9, 16.5, 1.5, 9)
        p.drawPath(path)
        p.drawEllipse(QPointF(9, 9), 2.5, 2.5)
    elif kind == "grid":
        p.drawRoundedRect(QRectF(2.5, 2.5, 13, 13), 2, 2)
        for x in (6.8, 11.2):
            p.drawLine(QPointF(x, 2.5), QPointF(x, 15.5))
            p.drawLine(QPointF(2.5, x), QPointF(15.5, x))
    elif kind == "focus":
        for (x, y, dx, dy) in ((2.5, 2.5, 1, 1), (15.5, 2.5, -1, 1),
                               (2.5, 15.5, 1, -1), (15.5, 15.5, -1, -1)):
            p.drawLine(QPointF(x, y), QPointF(x + 4 * dx, y))
            p.drawLine(QPointF(x, y), QPointF(x, y + 4 * dy))
        p.drawEllipse(QPointF(9, 9), 1.2, 1.2)
    elif kind == "plug":
        p.drawLine(QPointF(7, 2.5), QPointF(7, 6))
        p.drawLine(QPointF(11, 2.5), QPointF(11, 6))
        path = QPainterPath()
        path.moveTo(4.5, 6)
        path.lineTo(13.5, 6)
        path.lineTo(13.5, 9)
        path.quadTo(13.5, 12.5, 9, 12.5)
        path.quadTo(4.5, 12.5, 4.5, 9)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(QPointF(9, 12.5), QPointF(9, 16))
    p.end()
    pm.setDevicePixelRatio(scale)
    return QIcon(pm)


# ------------------------------------------------------------------ traffic lights
class TrafficLights(QWidget):
    close_clicked = Signal()
    minimize_clicked = Signal()
    zoom_clicked = Signal()

    COLORS = (("#FF5F57", "#E0443E"), ("#FEBC2E", "#DEA123"), ("#28C840", "#1AAB29"))
    D = 12
    GAP = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.D * 3 + self.GAP * 2 + 2, self.D + 2)
        self.setMouseTracking(True)
        self._hover = False
        self._pressed = -1
        self.active = True

    def _index_at(self, x):
        for i in range(3):
            left = 1 + i * (self.D + self.GAP)
            if left - 2 <= x <= left + self.D + 2:
                return i
        return -1

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def mousePressEvent(self, e):
        self._pressed = self._index_at(e.position().x())
        self.update()

    def mouseReleaseEvent(self, e):
        idx = self._index_at(e.position().x())
        if idx == self._pressed:
            (self.close_clicked, self.minimize_clicked, self.zoom_clicked)[idx].emit()
        self._pressed = -1
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        for i, (fill, edge) in enumerate(self.COLORS):
            r = QRectF(1 + i * (self.D + self.GAP), 1, self.D, self.D)
            if self.active or self._hover:
                c = QColor(fill)
                if self._pressed == i:
                    c = c.darker(120)
                p.setBrush(c)
                p.setPen(QPen(QColor(edge), 0.6))
            else:
                p.setBrush(QColor(0, 0, 0, 40))
                p.setPen(QPen(QColor(0, 0, 0, 30), 0.6))
            p.drawEllipse(r)
            if self._hover:
                p.setPen(QPen(QColor(0, 0, 0, 150), 1.2, Qt.SolidLine, Qt.RoundCap))
                c = r.center()
                if i == 0:
                    p.drawLine(c + QPointF(-2.6, -2.6), c + QPointF(2.6, 2.6))
                    p.drawLine(c + QPointF(-2.6, 2.6), c + QPointF(2.6, -2.6))
                elif i == 1:
                    p.drawLine(c + QPointF(-3.2, 0), c + QPointF(3.2, 0))
                else:
                    p.setPen(Qt.NoPen)
                    p.setBrush(QColor(0, 0, 0, 150))
                    tri = QPainterPath()
                    tri.moveTo(c + QPointF(-3, -3))
                    tri.lineTo(c + QPointF(1.6, -3))
                    tri.lineTo(c + QPointF(-3, 1.6))
                    tri.closeSubpath()
                    tri.moveTo(c + QPointF(3, 3))
                    tri.lineTo(c + QPointF(-1.6, 3))
                    tri.lineTo(c + QPointF(3, -1.6))
                    tri.closeSubpath()
                    p.drawPath(tri)


# ------------------------------------------------------------------ switch
class Switch(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(38, 22)
        self._pos = 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)
        self.theme = LIGHT

    def _animate(self, on):
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def setChecked(self, on):
        super().setChecked(on)
        self._anim.stop()
        self._pos = 1.0 if on else 0.0
        self.update()

    def get_knob(self):
        return self._pos

    def set_knob(self, v):
        self._pos = v
        self.update()

    knob = Property(float, get_knob, set_knob)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        off = QColor(self.theme["controlBorder"])
        on = QColor(self.theme["accent"])
        t = self._pos
        track = QColor(int(off.red() + (on.red() - off.red()) * t),
                       int(off.green() + (on.green() - off.green()) * t),
                       int(off.blue() + (on.blue() - off.blue()) * t))
        p.setPen(Qt.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(QRectF(0, 0, 38, 22), 11, 11)
        x = 2 + t * 16
        p.setBrush(QColor(0, 0, 0, 40))
        p.drawEllipse(QRectF(x, 2.6, 18, 18))
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QRectF(x, 2, 18, 18))

    def sizeHint(self):
        return QSize(38, 22)


# ------------------------------------------------------------------ popup button
class PopupButton(QComboBox):
    """QComboBox drawn like an NSPopUpButton (up/down chevrons)."""

    value_chosen = Signal(int, int)

    def __init__(self, prop_id, table, parent=None):
        super().__init__(parent)
        self.prop_id = prop_id
        self.table = table
        self.theme = LIGHT
        self.setCursor(Qt.PointingHandCursor)
        self.setEnabled(False)
        self.activated.connect(lambda i: self.value_chosen.emit(self.prop_id, self.itemData(i)))
        popup = self.view().window()
        popup.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        popup.setAttribute(Qt.WA_TranslucentBackground)

    def set_options(self, values, label_fn):
        current = self.currentData()
        self.blockSignals(True)
        self.clear()
        for v in values:
            self.addItem(label_fn(self.table, v), v)
        if current is not None:
            idx = self.findData(current)
            if idx >= 0:
                self.setCurrentIndex(idx)
        self.blockSignals(False)
        self.setEnabled(len(values) > 1)

    def set_value(self, value, label_fn):
        self.blockSignals(True)
        idx = self.findData(value)
        if idx < 0:
            self.addItem(label_fn(self.table, value), value)
            idx = self.count() - 1
        self.setCurrentIndex(idx)
        self.blockSignals(False)

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        color = QColor(self.theme["text"] if self.isEnabled() else self.theme["secondary"])
        p.setPen(QPen(color, 1.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        cx = self.width() - 14
        cy = self.height() / 2
        p.drawPolyline([QPointF(cx - 3, cy - 2), QPointF(cx, cy - 5), QPointF(cx + 3, cy - 2)])
        p.drawPolyline([QPointF(cx - 3, cy + 2), QPointF(cx, cy + 5), QPointF(cx + 3, cy + 2)])


# ------------------------------------------------------------------ shutter
class ShutterButton(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(66, 66)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Take photo (Space)")
        self.theme = LIGHT
        self._flash = 0.0

    def flash(self):
        self._flash = 1.0
        anim = QPropertyAnimation(self, b"flashLevel", self)
        anim.setDuration(350)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.start(QPropertyAnimation.DeleteWhenStopped)

    def get_flash(self):
        return self._flash

    def set_flash(self, v):
        self._flash = v
        self.update()

    flashLevel = Property(float, get_flash, set_flash)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        ring = QColor(self.theme["controlBorder"])
        p.setPen(QPen(ring, 3))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(2.5, 2.5, 61, 61))
        red = QColor("#FF3B30") if self.isEnabled() else QColor(self.theme["controlBorder"])
        if self.isDown():
            red = red.darker(115)
        inset = 8 if not self.isDown() else 10
        p.setPen(Qt.NoPen)
        p.setBrush(red)
        p.drawEllipse(QRectF(inset, inset, 66 - 2 * inset, 66 - 2 * inset))
        if self._flash > 0:
            p.setBrush(QColor(255, 255, 255, int(160 * self._flash)))
            p.drawEllipse(QRectF(inset, inset, 66 - 2 * inset, 66 - 2 * inset))
        make_icon("camera", "#FFFFFF", 24).paint(p, 21, 21, 24, 24)

    def sizeHint(self):
        return QSize(66, 66)


# ------------------------------------------------------------------ live view
class LiveView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme = LIGHT
        self.image = None
        self.show_grid = False
        self.placeholder_title = "No camera connected"
        self.placeholder_text = "Connect your Canon EOS 90D with a USB cable and turn it on."
        self._toast = ""
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._clear_toast)
        self.setMinimumSize(480, 320)

    def set_frame(self, image):
        self.image = image
        self.update()

    def clear_frame(self):
        self.image = None
        self.update()

    def set_placeholder(self, title, text):
        self.placeholder_title = title
        self.placeholder_text = text
        self.update()

    def toast(self, text, ms=2200):
        self._toast = text
        self._toast_timer.start(ms)
        self.update()

    def _clear_toast(self):
        self._toast = ""
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        rect = QRectF(self.rect())
        clip = QPainterPath()
        clip.addRoundedRect(rect, 12, 12)
        p.setClipPath(clip)
        p.fillRect(rect, QColor(self.theme["live"]))

        if self.image is not None:
            img = self.image
            s = min(rect.width() / img.width(), rect.height() / img.height())
            w, h = img.width() * s, img.height() * s
            target = QRectF((rect.width() - w) / 2, (rect.height() - h) / 2, w, h)
            p.drawImage(target, img)
            if self.show_grid:
                p.setPen(QPen(QColor(255, 255, 255, 90), 1))
                for i in (1, 2):
                    x = target.left() + target.width() * i / 3
                    y = target.top() + target.height() * i / 3
                    p.drawLine(QPointF(x, target.top()), QPointF(x, target.bottom()))
                    p.drawLine(QPointF(target.left(), y), QPointF(target.right(), y))
        else:
            make_icon("camera", "#8E8E93", 56).paint(
                p, int(rect.center().x() - 28), int(rect.center().y() - 70), 56, 56)
            f = QFont(UI_FONT)
            f.setPixelSize(17)
            f.setWeight(QFont.DemiBold)
            p.setFont(f)
            p.setPen(QColor("#E5E5EA"))
            p.drawText(QRectF(0, rect.center().y() - 6, rect.width(), 26),
                       Qt.AlignHCenter, self.placeholder_title)
            f.setPixelSize(13)
            f.setWeight(QFont.Normal)
            p.setFont(f)
            p.setPen(QColor("#8E8E93"))
            p.drawText(QRectF(40, rect.center().y() + 24, rect.width() - 80, 60),
                       Qt.AlignHCenter | Qt.TextWordWrap, self.placeholder_text)

        if self._toast:
            f = QFont(UI_FONT)
            f.setPixelSize(13)
            f.setWeight(QFont.Medium)
            p.setFont(f)
            tw = p.fontMetrics().horizontalAdvance(self._toast) + 36
            box = QRectF((rect.width() - tw) / 2, rect.height() - 58, tw, 36)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(30, 30, 32, 215))
            p.drawRoundedRect(box, 18, 18)
            p.setPen(QColor("#FFFFFF"))
            p.drawText(box, Qt.AlignCenter, self._toast)


# ------------------------------------------------------------------ grouped card
class Card(QFrame):
    """Inset grouped list like macOS System Settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 2, 12, 2)
        self._layout.setSpacing(0)
        self._rows = 0

    def add_row(self, label, widget=None):
        if self._rows:
            sep = QFrame()
            sep.setObjectName("rowSep")
            self._layout.addWidget(sep)
        row = QWidget()
        row.setAttribute(Qt.WA_TranslucentBackground)
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 7, 0, 7)
        h.setSpacing(8)
        if label is not None:
            lab = QLabel(label)
            lab.setObjectName("rowLabel")
            h.addWidget(lab)
            h.addStretch(1)
        if widget is not None:
            h.addWidget(widget, 0 if label is not None else 1)
        self._layout.addWidget(row)
        self._rows += 1
        return row


def value_label(text="—"):
    lab = QLabel(text)
    lab.setObjectName("rowValue")
    lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return lab


def section_header(text):
    lab = QLabel(text)
    lab.setObjectName("sectionHeader")
    return lab
