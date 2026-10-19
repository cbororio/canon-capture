"""Canon Capture: tethered photo capture for Canon EOS cameras."""

import os
import subprocess
import sys

from PySide6.QtCore import QSettings, QSize, Qt, QTimer
from PySide6.QtGui import (QColor, QFont, QGuiApplication, QIcon, QImage,
                           QImageReader, QKeySequence, QPainter, QPixmap,
                           QShortcut)
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QListView, QListWidget,
                               QListWidgetItem, QMenu, QPushButton, QScrollArea,
                               QToolButton, QVBoxLayout, QWidget)

from . import edsdk as eds
from . import props
from .camera import CameraController
from .chrome import FramelessWindow
from .widgets import (DARK, LIGHT, UI_FONT, Card, LiveView, PopupButton,
                      ShutterButton, Switch, TrafficLights, make_icon,
                      section_header, stylesheet, value_label)

APP_NAME = "Canon Capture"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".heif", ".heic"}
RAW_EXTS = {".cr3", ".cr2", ".crw"}
THUMB = QSize(132, 88)


def drag_area(widget):
    widget.setProperty("dragArea", True)
    return widget


def raw_preview(path):
    """Canon RAW files embed JPEG previews; decode the first one found."""
    try:
        with open(path, "rb") as f:
            data = f.read(4 * 1024 * 1024)
    except OSError:
        return None
    start = 0
    for _ in range(12):
        idx = data.find(b"\xff\xd8\xff", start)
        if idx < 0:
            break
        img = QImage.fromData(data[idx:], "JPG")
        if not img.isNull() and img.width() >= 120:
            return img
        start = idx + 3
    return None


def load_thumbnail(path):
    ext = os.path.splitext(path)[1].lower()
    img = None
    if ext in RAW_EXTS:
        img = raw_preview(path)
    else:
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        size = reader.size()
        if size.isValid():
            reader.setScaledSize(size.scaled(THUMB * 2, Qt.KeepAspectRatioByExpanding))
        img = reader.read()
    pm = QPixmap(THUMB * 2)
    pm.fill(QColor("#2C2C2E"))
    p = QPainter(pm)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.setRenderHint(QPainter.Antialiasing)
    if img is not None and not img.isNull():
        scaled = img.scaled(pm.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        p.drawImage((pm.width() - scaled.width()) // 2, (pm.height() - scaled.height()) // 2, scaled)
    if ext in RAW_EXTS:
        f = QFont(UI_FONT)
        f.setPixelSize(18)
        f.setBold(True)
        p.setFont(f)
        badge = ext[1:].upper()
        w = p.fontMetrics().horizontalAdvance(badge) + 16
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 150))
        p.drawRoundedRect(pm.width() - w - 8, pm.height() - 34, w, 26, 6, 6)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(pm.width() - w - 8, pm.height() - 34, w, 26, Qt.AlignCenter, badge)
    p.end()
    pm.setDevicePixelRatio(2)
    return QIcon(pm)


class MainWindow(FramelessWindow):
    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1000, 660)
        self.settings = QSettings("CanonCapture", "CanonCapture")
        self.theme = LIGHT
        self.session_count = 0
        self._thumb_queue = []

        self.camera = CameraController(self)
        self._build()
        self._load_settings()
        self._wire()
        self.apply_theme()
        QGuiApplication.styleHints().colorSchemeChanged.connect(lambda _: self.apply_theme())

    # ------------------------------------------------------------------ layout
    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())
        root.addWidget(self._build_content(), 1)

    def _build_sidebar(self):
        side = drag_area(QWidget())
        side.setObjectName("sidebar")
        side.setAttribute(Qt.WA_StyledBackground)
        side.setFixedWidth(290)
        v = QVBoxLayout(side)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        top = drag_area(QWidget())
        top.setFixedHeight(52)
        th = QHBoxLayout(top)
        th.setContentsMargins(18, 0, 18, 0)
        self.lights = TrafficLights()
        th.addWidget(self.lights)
        th.addStretch(1)
        v.addWidget(top)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)
        scroll.viewport().setStyleSheet("background: transparent;")
        body = drag_area(QWidget())
        body.setAttribute(Qt.WA_TranslucentBackground)
        b = QVBoxLayout(body)
        b.setContentsMargins(14, 0, 14, 14)
        b.setSpacing(6)

        b.addWidget(section_header("CAMERA"))
        card = Card()
        self.model_value = value_label()
        self.mode_value = value_label()
        self.battery_value = value_label()
        self.shots_value = value_label()
        card.add_row("Model", self.model_value)
        card.add_row("Mode", self.mode_value)
        card.add_row("Battery", self.battery_value)
        card.add_row("Shots left", self.shots_value)
        b.addWidget(card)
        b.addSpacing(10)

        b.addWidget(section_header("EXPOSURE"))
        card = Card()
        self.popups = {}
        for label, pid, table in (
            ("ISO", eds.kEdsPropID_ISOSpeed, props.ISO),
            ("Aperture", eds.kEdsPropID_Av, props.AV),
            ("Shutter speed", eds.kEdsPropID_Tv, props.TV),
            ("Exposure", eds.kEdsPropID_ExposureCompensation, props.exposure_comp),
            ("White balance", eds.kEdsPropID_WhiteBalance, props.WB),
        ):
            popup = PopupButton(pid, table)
            popup.setFixedWidth(140)
            self.popups[pid] = popup
            card.add_row(label, popup)
        b.addWidget(card)
        b.addSpacing(10)

        b.addWidget(section_header("CAPTURE"))
        card = Card()
        self.skip_af = Switch()
        self.keep_on_card = Switch()
        card.add_row("Skip autofocus", self.skip_af)
        card.add_row("Keep copy on SD card", self.keep_on_card)
        b.addWidget(card)
        b.addSpacing(10)

        b.addWidget(section_header("SAVE PHOTOS TO"))
        card = Card()
        folder_row = QWidget()
        fr = QHBoxLayout(folder_row)
        fr.setContentsMargins(0, 0, 0, 0)
        fr.setSpacing(8)
        icon = QLabel()
        icon.setPixmap(make_icon("folder", "#007AFF", 18).pixmap(18, 18))
        self.folder_label = QLabel()
        self.folder_label.setObjectName("rowLabel")
        self.folder_label.setMinimumWidth(60)
        self.choose_btn = QPushButton("Choose…")
        fr.addWidget(icon)
        fr.addWidget(self.folder_label, 1)
        fr.addWidget(self.choose_btn)
        card.add_row(None, folder_row)
        self.prefix_edit = QLineEdit()
        self.prefix_edit.setPlaceholderText("Keep camera name")
        self.prefix_edit.setFixedWidth(140)
        card.add_row("Name prefix", self.prefix_edit)
        b.addWidget(card)
        self.name_hint = QLabel()
        self.name_hint.setProperty("class", "secondary")
        self.name_hint.setWordWrap(True)
        self.name_hint.setContentsMargins(6, 2, 6, 0)
        b.addWidget(self.name_hint)
        b.addStretch(1)
        scroll.setWidget(body)
        v.addWidget(scroll, 1)

        status = drag_area(QWidget())
        status.setFixedHeight(40)
        sh = QHBoxLayout(status)
        sh.setContentsMargins(20, 0, 20, 4)
        sh.setSpacing(8)
        self.status_dot = QLabel()
        self.status_dot.setFixedSize(8, 8)
        self.status_text = drag_area(QLabel("Not connected"))
        self.status_text.setProperty("class", "secondary")
        sh.addWidget(self.status_dot)
        sh.addWidget(self.status_text, 1)
        v.addWidget(status)
        return side

    def _build_content(self):
        content = QWidget()
        content.setObjectName("content")
        content.setAttribute(Qt.WA_StyledBackground)
        v = QVBoxLayout(content)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        bar = drag_area(QWidget())
        bar.setObjectName("toolbar")
        bar.setAttribute(Qt.WA_StyledBackground)
        bar.setFixedHeight(52)
        h = QHBoxLayout(bar)
        h.setContentsMargins(20, 0, 14, 0)
        h.setSpacing(4)
        titles = drag_area(QWidget())
        tv = QVBoxLayout(titles)
        tv.setContentsMargins(0, 0, 0, 0)
        tv.setSpacing(0)
        self.title = drag_area(QLabel(APP_NAME))
        self.title.setObjectName("title")
        self.subtitle = drag_area(QLabel("No camera"))
        self.subtitle.setObjectName("subtitle")
        tv.addWidget(self.title)
        tv.addWidget(self.subtitle)
        h.addWidget(titles)
        h.addStretch(1)

        def tool(text, icon, tip, checkable=False):
            btn = QToolButton()
            btn.setText(text)
            btn.setToolTip(tip)
            btn.setCheckable(checkable)
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            btn.setIconSize(QSize(18, 18))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("iconKind", icon)
            h.addWidget(btn)
            return btn

        self.live_btn = tool("Live View", "eye", "Show live view (L)", True)
        self.grid_btn = tool("Grid", "grid", "Rule-of-thirds grid (G)", True)
        self.focus_btn = tool("Focus", "focus", "Autofocus (F)")
        sep = QFrame()
        sep.setFixedSize(1, 22)
        sep.setObjectName("rowSep")
        sep.setStyleSheet("max-height: 22px; min-height: 22px;")
        h.addSpacing(6)
        h.addWidget(sep)
        h.addSpacing(6)
        self.open_btn = tool("Open Folder", "folder", "Open the destination folder")
        self.tool_buttons = [self.live_btn, self.grid_btn, self.focus_btn, self.open_btn]
        v.addWidget(bar)

        stage = QWidget()
        stage.setObjectName("stage")
        stage.setAttribute(Qt.WA_StyledBackground)
        sv = QVBoxLayout(stage)
        sv.setContentsMargins(22, 18, 22, 12)
        sv.setSpacing(14)

        self.banner = QFrame()
        self.banner.setObjectName("banner")
        bh = QHBoxLayout(self.banner)
        bh.setContentsMargins(16, 12, 12, 12)
        bh.setSpacing(12)
        btxt = QVBoxLayout()
        btxt.setSpacing(2)
        bt = QLabel("Canon EDSDK not found")
        bt.setObjectName("bannerTitle")
        self.banner_text = QLabel()
        self.banner_text.setProperty("class", "secondary")
        self.banner_text.setWordWrap(True)
        self.banner_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        btxt.addWidget(bt)
        btxt.addWidget(self.banner_text)
        bh.addLayout(btxt, 1)
        self.banner_open = QPushButton("Show Folder")
        self.banner_retry = QPushButton("Try Again")
        self.banner_retry.setObjectName("primary")
        bh.addWidget(self.banner_open)
        bh.addWidget(self.banner_retry)
        self.banner.hide()
        sv.addWidget(self.banner)

        self.live = LiveView()
        sv.addWidget(self.live, 1)

        controls = QHBoxLayout()
        controls.setSpacing(12)
        self.counter = QLabel("No photos yet")
        self.counter.setObjectName("counter")
        self.shutter = ShutterButton()
        self.shutter.setEnabled(False)
        hint = QLabel("Space to shoot  ·  F to focus")
        hint.setObjectName("counter")
        hint.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        controls.addWidget(self.counter, 1)
        controls.addWidget(self.shutter)
        controls.addWidget(hint, 1)
        sv.addLayout(controls)

        self.strip = QListWidget()
        self.strip.setViewMode(QListView.IconMode)
        self.strip.setFlow(QListView.LeftToRight)
        self.strip.setWrapping(False)
        self.strip.setMovement(QListView.Static)
        self.strip.setIconSize(THUMB)
        self.strip.setGridSize(QSize(THUMB.width() + 12, THUMB.height() + 12))
        self.strip.setFixedHeight(THUMB.height() + 26)
        self.strip.setHorizontalScrollMode(QListView.ScrollPerPixel)
        self.strip.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.strip.setContextMenuPolicy(Qt.CustomContextMenu)
        sv.addWidget(self.strip)
        v.addWidget(stage, 1)
        return content

    # ------------------------------------------------------------------ wiring
    def _wire(self):
        self.lights.close_clicked.connect(self.close)
        self.lights.minimize_clicked.connect(self.showMinimized)
        self.lights.zoom_clicked.connect(self.toggle_maximized)

        c = self.camera
        c.sdk_missing.connect(self._on_sdk_missing)
        c.connected.connect(self._on_connected)
        c.disconnected.connect(self._on_disconnected)
        c.message.connect(lambda m: self.live.toast(m, 3500))
        c.error.connect(lambda m: self.live.toast(m, 4500))
        c.property_changed.connect(self._on_property)
        c.property_options.connect(self._on_options)
        c.liveview_frame.connect(self.live.set_frame)
        c.liveview_state.connect(self._on_liveview_state)
        c.photo_saved.connect(self._on_photo_saved)

        for popup in self.popups.values():
            popup.value_chosen.connect(c.set_property)
        self.shutter.clicked.connect(self.capture)
        self.focus_btn.clicked.connect(c.autofocus)
        self.live_btn.toggled.connect(self._toggle_live)
        self.grid_btn.toggled.connect(self._toggle_grid)
        self.open_btn.clicked.connect(lambda: self._open_path(self.camera.destination))
        self.choose_btn.clicked.connect(self.choose_folder)
        self.prefix_edit.textChanged.connect(self._prefix_changed)
        self.skip_af.toggled.connect(lambda on: self.settings.setValue("skip_af", on))
        self.keep_on_card.toggled.connect(self._keep_changed)
        self.banner_open.clicked.connect(lambda: self._open_path(eds.candidate_dirs()[0]))
        self.banner_retry.clicked.connect(self._retry_sdk)
        self.strip.itemDoubleClicked.connect(lambda it: self._open_path(it.data(Qt.UserRole)))
        self.strip.customContextMenuRequested.connect(self._strip_menu)

        for key, fn in (("Space", self.capture), ("F", c.autofocus),
                        ("L", self.live_btn.toggle), ("G", self.grid_btn.toggle),
                        ("Ctrl+O", self.choose_folder)):
            QShortcut(QKeySequence(key), self, activated=fn)

        self._thumb_timer = QTimer(self)
        self._thumb_timer.setInterval(0)
        self._thumb_timer.timeout.connect(self._process_thumb)

    def _load_settings(self):
        s = self.settings
        dest = s.value("destination", self.camera.destination)
        prefix = s.value("prefix", "")
        self.camera.set_destination(dest, prefix)
        self.prefix_edit.setText(prefix)
        self.skip_af.setChecked(s.value("skip_af", False, type=bool))
        self.keep_on_card.setChecked(s.value("keep_on_card", False, type=bool))
        self.camera.keep_on_card = self.keep_on_card.isChecked()
        self.live_btn.setChecked(s.value("liveview", True, type=bool))
        self.grid_btn.setChecked(s.value("grid", False, type=bool))
        self.live.show_grid = self.grid_btn.isChecked()
        geo = s.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        else:
            self.resize(1320, 860)
        self._update_folder_label()
        self._load_existing_photos()

    # ------------------------------------------------------------------ theme
    def apply_theme(self):
        forced = os.environ.get("CANON_CAPTURE_THEME", "").lower()
        if forced in ("light", "dark"):
            dark = forced == "dark"
        else:
            dark = QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
        self.theme = DARK if dark else LIGHT
        QApplication.instance().setStyleSheet(stylesheet(self.theme))
        for w in (self.skip_af, self.keep_on_card, self.shutter, self.live, *self.popups.values()):
            w.theme = self.theme
            w.update()
        for btn in self.tool_buttons:
            btn.setIcon(make_icon(btn.property("iconKind"), self.theme["text"]))
        self._update_status_dot()

    def _update_status_dot(self):
        color = "#34C759" if self.camera.is_connected else self.theme["controlBorder"]
        self.status_dot.setStyleSheet(f"background: {color}; border-radius: 4px;")

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == e.Type.ActivationChange:
            self.lights.active = self.isActiveWindow()
            self.lights.update()

    # ------------------------------------------------------------------ camera events
    def _on_sdk_missing(self):
        folder = eds.candidate_dirs()[0]
        self.banner_text.setText(
            "Copy EDSDK.dll and EdsImage.dll (64-bit, from Canon's developer SDK) into:\n"
            f"{folder}")
        self.banner.show()
        self.live.set_placeholder("Camera SDK missing",
                                  "Add the Canon SDK files shown above, then click Try Again.")
        self.status_text.setText("SDK not installed")

    def _retry_sdk(self):
        if self.camera.start():
            self.banner.hide()
            self.live.set_placeholder("No camera connected",
                                      "Connect your Canon EOS 90D with a USB cable and turn it on.")
            self.status_text.setText("Waiting for camera…")

    def _on_connected(self, model):
        self.model_value.setText(model)
        self.subtitle.setText(f"{model}  ·  Connected")
        self.status_text.setText(f"{model} connected via USB")
        self.shutter.setEnabled(True)
        self.live.set_placeholder("Live view is off", "Turn on Live View in the toolbar, or just press the shutter.")
        self._update_status_dot()
        if self.live_btn.isChecked():
            QTimer.singleShot(300, self.camera.start_liveview)

    def _on_disconnected(self):
        self.subtitle.setText("No camera")
        self.status_text.setText("Waiting for camera…")
        for lab in (self.model_value, self.mode_value, self.battery_value, self.shots_value):
            lab.setText("—")
        for popup in self.popups.values():
            popup.clear()
            popup.setEnabled(False)
        self.shutter.setEnabled(False)
        self.live.clear_frame()
        self.live.set_placeholder("No camera connected",
                                  "Connect your Canon EOS 90D with a USB cable and turn it on.")
        self._update_status_dot()

    def _on_property(self, pid, value):
        if pid in self.popups:
            self.popups[pid].set_value(value, props.label)
        elif pid == eds.kEdsPropID_AEMode:
            self.mode_value.setText(props.label(props.AE_MODE, value))
        elif pid == eds.kEdsPropID_BatteryLevel:
            self.battery_value.setText("AC power" if value == 0xFFFFFFFF else f"{value}%")
        elif pid == eds.kEdsPropID_AvailableShots:
            self.shots_value.setText(f"{value:,}")

    def _on_options(self, pid, values):
        if pid in self.popups:
            self.popups[pid].set_options(values, props.label)

    def _on_liveview_state(self, on):
        if not on:
            self.live.clear_frame()
        self.live_btn.blockSignals(True)
        self.live_btn.setChecked(on)
        self.live_btn.blockSignals(False)

    def _on_photo_saved(self, path):
        self.session_count += 1
        n = self.session_count
        self.counter.setText(f"{n} photo{'s' if n != 1 else ''} this session")
        self.live.toast(f"Saved {os.path.basename(path)}")
        self._add_thumb(path, front=True)

    # ------------------------------------------------------------------ actions
    def capture(self):
        if not self.camera.is_connected:
            self.live.toast("No camera connected")
            return
        self.shutter.flash()
        self.camera.capture(skip_af=self.skip_af.isChecked())

    def _toggle_live(self, on):
        self.settings.setValue("liveview", on)
        if on:
            self.camera.start_liveview()
        else:
            self.camera.stop_liveview()

    def _toggle_grid(self, on):
        self.settings.setValue("grid", on)
        self.live.show_grid = on
        self.live.update()

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose where to save photos",
                                                  self.camera.destination)
        if folder:
            folder = os.path.normpath(folder)
            self.settings.setValue("destination", folder)
            self.camera.set_destination(folder, self.prefix_edit.text())
            self._update_folder_label()
            self._load_existing_photos()

    def _prefix_changed(self, text):
        self.settings.setValue("prefix", text)
        self.camera.set_destination(self.camera.destination, text)
        self._update_folder_label()

    def _keep_changed(self, on):
        self.settings.setValue("keep_on_card", on)
        self.camera.set_keep_on_card(on)

    def _update_folder_label(self):
        dest = self.camera.destination
        name = os.path.basename(dest.rstrip("\\/")) or dest
        self.folder_label.setText(name)
        self.folder_label.setToolTip(dest)
        prefix = self.prefix_edit.text().strip()
        example = f"{prefix}_20261007_142233.JPG" if prefix else "IMG_1234.JPG"
        self.name_hint.setText(f"{dest}\nFiles are named like {example}")

    def _open_path(self, path):
        if path and os.path.exists(path):
            os.startfile(path)

    def _strip_menu(self, pos):
        item = self.strip.itemAt(pos)
        if not item:
            return
        path = item.data(Qt.UserRole)
        menu = QMenu(self)
        menu.addAction("Open", lambda: self._open_path(path))
        menu.addAction("Show in Folder",
                       lambda: subprocess.Popen(["explorer", "/select,", os.path.normpath(path)]))
        menu.exec(self.strip.mapToGlobal(pos))

    # ------------------------------------------------------------------ filmstrip
    def _load_existing_photos(self):
        self.strip.clear()
        self._thumb_queue.clear()
        dest = self.camera.destination
        try:
            entries = [e for e in os.scandir(dest) if e.is_file()
                       and os.path.splitext(e.name)[1].lower() in IMAGE_EXTS | RAW_EXTS]
        except OSError:
            return
        entries.sort(key=lambda e: e.stat().st_mtime, reverse=True)
        for e in entries[:60]:
            self._add_thumb(e.path)

    def _add_thumb(self, path, front=False):
        item = QListWidgetItem()
        item.setData(Qt.UserRole, path)
        item.setToolTip(os.path.basename(path))
        item.setSizeHint(QSize(THUMB.width() + 8, THUMB.height() + 8))
        if front:
            self.strip.insertItem(0, item)
            self.strip.scrollToTop()
            item.setIcon(load_thumbnail(path))
        else:
            self.strip.addItem(item)
            self._thumb_queue.append(item)
            self._thumb_timer.start()

    def _process_thumb(self):
        if not self._thumb_queue:
            self._thumb_timer.stop()
            return
        item = self._thumb_queue.pop(0)
        if self.strip.row(item) >= 0:
            item.setIcon(load_thumbnail(item.data(Qt.UserRole)))

    # ------------------------------------------------------------------ shutdown
    def closeEvent(self, e):
        self.settings.setValue("geometry", self.saveGeometry())
        self.camera.shutdown()
        super().closeEvent(e)


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setFont(QFont(UI_FONT, 10))
    app.setWindowIcon(make_icon("camera", "#FF3B30", 64))
    win = MainWindow()
    win.show()
    QTimer.singleShot(0, win.camera.start)

    if "--screenshot" in sys.argv:
        out = sys.argv[sys.argv.index("--screenshot") + 1]
        QTimer.singleShot(1500, lambda: (win.grab().save(out), app.quit()))
    sys.exit(app.exec())
