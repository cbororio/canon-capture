"""Camera controller: owns the EDSDK session and exposes Qt signals.

All SDK calls run on the Qt main thread. On Windows the SDK delivers its
events through the thread's message loop, which Qt pumps for us.
"""

import os
import time

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QImage

from . import edsdk as eds
from .edsdk import EdsdkError

EXPOSURE_PROPS = (
    eds.kEdsPropID_ISOSpeed,
    eds.kEdsPropID_Av,
    eds.kEdsPropID_Tv,
    eds.kEdsPropID_ExposureCompensation,
    eds.kEdsPropID_WhiteBalance,
)
INFO_PROPS = (
    eds.kEdsPropID_AEMode,
    eds.kEdsPropID_BatteryLevel,
    eds.kEdsPropID_AvailableShots,
)


class CameraController(QObject):
    sdk_missing = Signal()
    connected = Signal(str)
    disconnected = Signal()
    message = Signal(str)
    error = Signal(str)
    property_changed = Signal(int, int)
    property_options = Signal(int, list)
    liveview_frame = Signal(QImage)
    liveview_state = Signal(bool)
    photo_saved = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sdk = None
        self.cam = None
        self.model = ""
        self.destination = os.path.join(os.path.expanduser("~"), "Pictures", "Canon Capture")
        self.prefix = ""
        self.keep_on_card = False
        self._evf = None
        self._live_timer = QTimer(self)
        self._live_timer.setInterval(40)
        self._live_timer.timeout.connect(self._pull_frame)
        self._retry_timer = QTimer(self)
        self._retry_timer.setInterval(2000)
        self._retry_timer.timeout.connect(self.try_connect)
        # ctypes callbacks must stay referenced for as long as the SDK may call them
        self._on_object = eds.ObjectHandler(self._handle_object)
        self._on_property = eds.PropertyHandler(self._handle_property)
        self._on_state = eds.StateHandler(self._handle_state)
        self._on_added = eds.CameraAddedHandler(self._handle_added)

    # ---------------------------------------------------------------- lifecycle
    def start(self):
        path = eds.find_dll()
        if not path:
            self.sdk_missing.emit()
            return False
        try:
            self.sdk = eds.EDSDK(path)
            self.sdk.initialize()
            self.sdk.set_camera_added_handler(self._on_added)
        except (OSError, EdsdkError) as exc:
            self.sdk = None
            self.error.emit(f"Could not load Canon EDSDK: {exc}")
            return False
        self.try_connect()
        self._retry_timer.start()
        return True

    def shutdown(self):
        self._retry_timer.stop()
        self.disconnect_camera(silent=True)
        if self.sdk:
            self.sdk.terminate()
            self.sdk = None

    @property
    def is_connected(self):
        return self.cam is not None

    def try_connect(self):
        if not self.sdk or self.cam:
            return
        try:
            cam = self.sdk.first_camera()
        except EdsdkError:
            return
        if not cam:
            return
        try:
            self.sdk.open_session(cam)
        except EdsdkError as exc:
            self.sdk.release(cam)
            if exc.code == eds.EDS_ERR_DEVICE_BUSY:
                self.message.emit("Camera is in use by another app (close EOS Utility)")
            return
        self.cam = cam
        try:
            self.model = self.sdk.device_description(cam)
        except EdsdkError:
            self.model = "Canon EOS"
        try:
            self.sdk.set_object_handler(cam, self._on_object)
            self.sdk.set_property_handler(cam, self._on_property)
            self.sdk.set_state_handler(cam, self._on_state)
        except EdsdkError as exc:
            self.error.emit(str(exc))
        self.apply_save_target()
        self.connected.emit(self.model)
        self.refresh_all()

    def disconnect_camera(self, silent=False):
        if not self.cam:
            return
        self.stop_liveview(restore=not silent)
        try:
            self.sdk.close_session(self.cam)
        finally:
            self.sdk.release(self.cam)
            self.cam = None
            self.disconnected.emit()

    # ---------------------------------------------------------------- properties
    def refresh_all(self):
        for pid in EXPOSURE_PROPS:
            self._refresh_desc(pid)
        for pid in EXPOSURE_PROPS + INFO_PROPS:
            self._refresh_value(pid)

    def _refresh_value(self, pid):
        if not self.cam:
            return
        try:
            value = self.sdk.get_uint32(self.cam, pid)
        except EdsdkError:
            if pid == eds.kEdsPropID_AEMode:
                try:
                    value = self.sdk.get_uint32(self.cam, eds.kEdsPropID_AEModeSelect)
                except EdsdkError:
                    return
            else:
                return
        self.property_changed.emit(pid, value)

    def _refresh_desc(self, pid):
        if not self.cam:
            return
        try:
            values = self.sdk.get_desc(self.cam, pid)
        except EdsdkError:
            values = []
        self.property_options.emit(pid, values)

    def set_property(self, pid, value):
        if not self.cam:
            return
        try:
            self.sdk.set_uint32(self.cam, pid, value)
        except EdsdkError as exc:
            self.error.emit(str(exc))
            self._refresh_value(pid)

    # ---------------------------------------------------------------- saving
    def set_destination(self, folder, prefix):
        self.destination = folder
        self.prefix = prefix.strip()

    def set_keep_on_card(self, keep):
        self.keep_on_card = keep
        self.apply_save_target()

    def apply_save_target(self):
        if not self.cam:
            return
        target = eds.kEdsSaveTo_Both if self.keep_on_card else eds.kEdsSaveTo_Host
        try:
            self.sdk.set_uint32(self.cam, eds.kEdsPropID_SaveTo, target)
            self.sdk.set_capacity(self.cam)
        except EdsdkError as exc:
            self.error.emit(f"Could not set save location: {exc}")

    def _target_path(self, camera_name):
        stem, ext = os.path.splitext(camera_name)
        if self.prefix:
            stem = f"{self.prefix}_{time.strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(self.destination, exist_ok=True)
        path = os.path.join(self.destination, stem + ext)
        n = 2
        while os.path.exists(path):
            path = os.path.join(self.destination, f"{stem}-{n}{ext}")
            n += 1
        return path

    # ---------------------------------------------------------------- shooting
    def capture(self, skip_af=False):
        if not self.cam:
            self.message.emit("No camera connected")
            return
        press = (eds.kEdsCameraCommand_ShutterButton_Completely_NonAF if skip_af
                 else eds.kEdsCameraCommand_ShutterButton_Completely)
        try:
            self.sdk.send_command(self.cam, eds.kEdsCameraCommand_PressShutterButton, press)
        except EdsdkError as exc:
            self.error.emit(str(exc))
        finally:
            self._release_shutter()

    def autofocus(self):
        if not self.cam:
            return
        try:
            self.sdk.send_command(self.cam, eds.kEdsCameraCommand_PressShutterButton,
                                  eds.kEdsCameraCommand_ShutterButton_Halfway)
        except EdsdkError as exc:
            self.error.emit(str(exc))
            self._release_shutter()
            return
        QTimer.singleShot(900, self._release_shutter)

    def _release_shutter(self):
        if not self.cam:
            return
        try:
            self.sdk.send_command(self.cam, eds.kEdsCameraCommand_PressShutterButton,
                                  eds.kEdsCameraCommand_ShutterButton_OFF)
        except EdsdkError:
            pass

    # ---------------------------------------------------------------- live view
    def start_liveview(self):
        if not self.cam or self._evf:
            return
        try:
            try:
                self.sdk.set_uint32(self.cam, eds.kEdsPropID_Evf_Mode, 1)
            except EdsdkError:
                pass
            device = self.sdk.get_uint32(self.cam, eds.kEdsPropID_Evf_OutputDevice)
            self.sdk.set_uint32(self.cam, eds.kEdsPropID_Evf_OutputDevice,
                                device | eds.kEdsEvfOutputDevice_PC)
            self._evf = self.sdk.create_evf()
        except EdsdkError as exc:
            self.error.emit(f"Live view failed: {exc}")
            return
        self._live_timer.start()
        self.liveview_state.emit(True)

    def stop_liveview(self, restore=True):
        if not self._evf:
            return
        self._live_timer.stop()
        stream, evf = self._evf
        self._evf = None
        self.sdk.release(evf)
        self.sdk.release(stream)
        if restore and self.cam:
            try:
                device = self.sdk.get_uint32(self.cam, eds.kEdsPropID_Evf_OutputDevice)
                self.sdk.set_uint32(self.cam, eds.kEdsPropID_Evf_OutputDevice,
                                    device & ~eds.kEdsEvfOutputDevice_PC)
            except EdsdkError:
                pass
        self.liveview_state.emit(False)

    def _pull_frame(self):
        if not self._evf or not self.cam:
            return
        stream, evf = self._evf
        try:
            data = self.sdk.download_evf(self.cam, stream, evf)
        except EdsdkError as exc:
            self.error.emit(f"Live view stopped: {exc}")
            self.stop_liveview()
            return
        if data:
            image = QImage.fromData(data, "JPG")
            if not image.isNull():
                self.liveview_frame.emit(image)

    # ---------------------------------------------------------------- SDK events
    def _handle_object(self, event, ref, _ctx):
        try:
            if event == eds.kEdsObjectEvent_DirItemRequestTransfer:
                self._download(ref)
        except Exception as exc:  # never let an exception escape into the SDK
            self.error.emit(f"Transfer failed: {exc}")
        finally:
            if ref:
                self.sdk.release(ref)
        return 0

    def _download(self, item):
        size, name = self.sdk.directory_item_info(item)
        path = self._target_path(name)
        self.sdk.download(item, size, path)
        self.photo_saved.emit(path)

    def _handle_property(self, event, pid, _param, _ctx):
        if event == eds.kEdsPropertyEvent_PropertyChanged:
            QTimer.singleShot(0, lambda: self._refresh_value(pid))
        elif event == eds.kEdsPropertyEvent_PropertyDescChanged and pid in EXPOSURE_PROPS:
            QTimer.singleShot(0, lambda: self._refresh_desc(pid))
        return 0

    def _handle_state(self, event, _data, _ctx):
        if event == eds.kEdsStateEvent_Shutdown:
            QTimer.singleShot(0, lambda: self.disconnect_camera(silent=True))
        elif event == eds.kEdsStateEvent_WillSoonShutDown and self.cam:
            try:
                self.sdk.send_command(self.cam, eds.kEdsCameraCommand_ExtendShutDownTimer, 0)
            except EdsdkError:
                pass
        return 0

    def _handle_added(self, _ctx):
        QTimer.singleShot(500, self.try_connect)
        return 0
