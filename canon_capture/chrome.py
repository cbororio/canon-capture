"""Frameless window with native Windows behaviour (snap, shadow, rounded
corners, resize) so we can draw a macOS-style title area ourselves."""

import ctypes
from ctypes import wintypes

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QWidget

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi

GWL_STYLE = -16
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WM_NCCALCSIZE = 0x0083
WM_NCHITTEST = 0x0084
HTCAPTION = 2
HT_EDGES = {
    (True, False, False, False): 10,  # left
    (False, True, False, False): 11,  # right
    (False, False, True, False): 12,  # top
    (True, False, True, False): 13,   # top-left
    (False, True, True, False): 14,   # top-right
    (False, False, False, True): 15,  # bottom
    (True, False, False, True): 16,   # bottom-left
    (False, True, False, True): 17,   # bottom-right
}
SM_CXSIZEFRAME = 32
SM_CYSIZEFRAME = 33
SM_CXPADDEDBORDER = 92
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2


class MARGINS(ctypes.Structure):
    _fields_ = [("left", ctypes.c_int), ("right", ctypes.c_int),
                ("top", ctypes.c_int), ("bottom", ctypes.c_int)]


class NCCALCSIZE_PARAMS(ctypes.Structure):
    _fields_ = [("rgrc", wintypes.RECT * 3), ("lppos", ctypes.c_void_p)]


user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]


class FramelessWindow(QWidget):
    RESIZE_BORDER = 6

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self._native_ready = False

    def showEvent(self, event):
        super().showEvent(event)
        if not self._native_ready:
            self._native_ready = True
            hwnd = int(self.winId())
            style = user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
            user32.SetWindowLongPtrW(hwnd, GWL_STYLE, style | WS_CAPTION | WS_THICKFRAME
                                     | WS_MINIMIZEBOX | WS_MAXIMIZEBOX)
            dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(MARGINS(1, 1, 1, 1)))
            pref = ctypes.c_int(DWMWCP_ROUND)
            dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                                         ctypes.byref(pref), ctypes.sizeof(pref))
            # SWP_FRAMECHANGED | NOMOVE | NOSIZE | NOZORDER | NOACTIVATE
            user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0020 | 0x0002 | 0x0001 | 0x0004 | 0x0010)

    def toggle_maximized(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _is_drag_area(self, pos):
        """Empty title-bar space: widgets flagged with the `dragArea` property."""
        child = self.childAt(pos)
        return child is not None and bool(child.property("dragArea"))

    def nativeEvent(self, event_type, message):
        if event_type != b"windows_generic_MSG":
            return False, 0
        msg = wintypes.MSG.from_address(int(message))

        if msg.message == WM_NCCALCSIZE and msg.wParam:
            if self.isMaximized():
                # Maximized windows overhang the monitor by the frame size; trim it.
                params = NCCALCSIZE_PARAMS.from_address(msg.lParam)
                fx = user32.GetSystemMetrics(SM_CXSIZEFRAME) + user32.GetSystemMetrics(SM_CXPADDEDBORDER)
                fy = user32.GetSystemMetrics(SM_CYSIZEFRAME) + user32.GetSystemMetrics(SM_CXPADDEDBORDER)
                r = params.rgrc[0]
                r.left += fx
                r.top += fy
                r.right -= fx
                r.bottom -= fy
            return True, 0

        if msg.message == WM_NCHITTEST:
            pos = self.mapFromGlobal(QCursor.pos())
            if not self.isMaximized():
                b = self.RESIZE_BORDER
                key = (pos.x() < b, pos.x() > self.width() - b,
                       pos.y() < b, pos.y() > self.height() - b)
                if key in HT_EDGES:
                    return True, HT_EDGES[key]
            if self._is_drag_area(pos):
                return True, HTCAPTION
        return False, 0
