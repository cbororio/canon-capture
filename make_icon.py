"""Render the app icon to CanonCapture.ico (used by the build)."""
import sys
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath
from PIL import Image

app = QGuiApplication(sys.argv)
from canon_capture.widgets import make_icon  # noqa: E402

size = 256
img = QImage(size, size, QImage.Format_ARGB32)
img.fill(Qt.transparent)
p = QPainter(img)
p.setRenderHint(QPainter.Antialiasing)
grad = QLinearGradient(0, 0, 0, size)
grad.setColorAt(0, QColor("#FF6B5E"))
grad.setColorAt(1, QColor("#E0302A"))
path = QPainterPath()
path.addRoundedRect(QRectF(16, 16, 224, 224), 52, 52)
p.fillPath(path, grad)
make_icon("camera", "#FFFFFF", 150).paint(p, 53, 53, 150, 150)
p.end()
img.save("build_icon.png")
Image.open("build_icon.png").save("CanonCapture.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
