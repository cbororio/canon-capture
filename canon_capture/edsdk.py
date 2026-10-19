"""Minimal ctypes bindings for the Canon EOS Digital SDK (EDSDK).

Only the calls needed for tethered photo capture are bound. The SDK DLLs
(EDSDK.dll and EdsImage.dll, 64-bit) are not redistributable, so they are
loaded at runtime from next to the executable or from an `EDSDK` folder.
"""

import ctypes
import os
import sys
from ctypes import (POINTER, Structure, WINFUNCTYPE, byref, c_char, c_int32,
                    c_uint32, c_uint64, c_void_p)

EdsError = c_uint32
EdsBaseRef = c_void_p

EDS_ERR_OK = 0x00000000
EDS_ERR_DEVICE_BUSY = 0x00000081
EDS_ERR_OBJECT_NOTREADY = 0x0000A102
EDS_ERR_TAKE_PICTURE_AF_NG = 0x00008D01

ERROR_NAMES = {
    0x00000002: "Internal SDK error",
    0x00000007: "Invalid parameter",
    0x00000060: "Property not supported by this camera",
    0x00000061: "Camera did not accept this value",
    0x00000081: "Camera is busy",
    0x00000086: "Device not found",
    0x000000C0: "Camera disconnected",
    0x00002003: "Session is not open",
    0x00008D01: "Autofocus failed - try again or enable 'Skip autofocus'",
    0x00008D02: "Mirror is locked up",
    0x00008D05: "No SD card in camera",
    0x00008D06: "SD card is write-protected",
    0x0000A102: "Live view frame not ready",
}

# Property IDs
kEdsPropID_ProductName = 0x00000002
kEdsPropID_BatteryLevel = 0x00000008
kEdsPropID_SaveTo = 0x0000000B
kEdsPropID_WhiteBalance = 0x00000106
kEdsPropID_AEMode = 0x00000400
kEdsPropID_ISOSpeed = 0x00000402
kEdsPropID_Av = 0x00000405
kEdsPropID_Tv = 0x00000406
kEdsPropID_ExposureCompensation = 0x00000407
kEdsPropID_AvailableShots = 0x0000040A
kEdsPropID_AEModeSelect = 0x00000436
kEdsPropID_Evf_OutputDevice = 0x00000500
kEdsPropID_Evf_Mode = 0x00000501

kEdsSaveTo_Camera = 1
kEdsSaveTo_Host = 2
kEdsSaveTo_Both = 3

kEdsEvfOutputDevice_TFT = 1
kEdsEvfOutputDevice_PC = 2

# Commands
kEdsCameraCommand_ExtendShutDownTimer = 0x00000001
kEdsCameraCommand_PressShutterButton = 0x00000004
kEdsCameraCommand_ShutterButton_OFF = 0x00000000
kEdsCameraCommand_ShutterButton_Halfway = 0x00000001
kEdsCameraCommand_ShutterButton_Completely = 0x00000003
kEdsCameraCommand_ShutterButton_Completely_NonAF = 0x00010003

# Events
kEdsPropertyEvent_All = 0x00000100
kEdsPropertyEvent_PropertyChanged = 0x00000101
kEdsPropertyEvent_PropertyDescChanged = 0x00000102
kEdsObjectEvent_All = 0x00000200
kEdsObjectEvent_DirItemRequestTransfer = 0x00000208
kEdsStateEvent_All = 0x00000300
kEdsStateEvent_Shutdown = 0x00000301
kEdsStateEvent_WillSoonShutDown = 0x00000303

kEdsFileCreateDisposition_CreateAlways = 1
kEdsAccess_ReadWrite = 2


class EdsDeviceInfo(Structure):
    _fields_ = [
        ("szPortName", c_char * 256),
        ("szDeviceDescription", c_char * 256),
        ("deviceSubType", c_uint32),
        ("reserved", c_uint32),
    ]


class EdsPropertyDesc(Structure):
    _fields_ = [
        ("form", c_int32),
        ("access", c_int32),
        ("numElements", c_int32),
        ("propDesc", c_int32 * 128),
    ]


class EdsCapacity(Structure):
    _fields_ = [
        ("numberOfFreeClusters", c_int32),
        ("bytesPerSector", c_int32),
        ("reset", c_int32),
    ]


ObjectHandler = WINFUNCTYPE(EdsError, c_uint32, EdsBaseRef, c_void_p)
PropertyHandler = WINFUNCTYPE(EdsError, c_uint32, c_uint32, c_uint32, c_void_p)
StateHandler = WINFUNCTYPE(EdsError, c_uint32, c_uint32, c_void_p)
CameraAddedHandler = WINFUNCTYPE(EdsError, c_void_p)


class EdsdkError(Exception):
    def __init__(self, func, code):
        self.code = code
        name = ERROR_NAMES.get(code, "Error")
        super().__init__(f"{name} (0x{code:08X}) in {func}")


def _app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def candidate_dirs():
    base = _app_dir()
    dirs = [base, os.path.join(base, "EDSDK")]
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        dirs.append(os.path.join(bundled, "EDSDK"))
    return dirs


def find_dll():
    for d in candidate_dirs():
        path = os.path.join(d, "EDSDK.dll")
        if os.path.isfile(path):
            return path
    return None


class EDSDK:
    """Thin wrapper that raises EdsdkError on non-zero return codes."""

    def __init__(self, dll_path):
        dll_dir = os.path.dirname(dll_path)
        os.add_dll_directory(dll_dir)
        os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")
        self.dll = ctypes.WinDLL(dll_path)
        for name in (
            "EdsInitializeSDK", "EdsTerminateSDK", "EdsGetCameraList",
            "EdsGetChildCount", "EdsGetChildAtIndex", "EdsGetDeviceInfo",
            "EdsOpenSession", "EdsCloseSession", "EdsRelease", "EdsRetain",
            "EdsGetPropertyData", "EdsSetPropertyData", "EdsGetPropertyDesc",
            "EdsGetPropertySize", "EdsSendCommand", "EdsSetCapacity",
            "EdsGetDirectoryItemInfo", "EdsCreateFileStream", "EdsDownload",
            "EdsDownloadComplete", "EdsCreateMemoryStream", "EdsCreateEvfImageRef",
            "EdsDownloadEvfImage", "EdsGetPointer", "EdsGetLength",
            "EdsSetObjectEventHandler", "EdsSetPropertyEventHandler",
            "EdsSetCameraStateEventHandler", "EdsSetCameraAddedHandler",
        ):
            getattr(self.dll, name).restype = EdsError

    def _call(self, name, *args):
        err = getattr(self.dll, name)(*args)
        if err != EDS_ERR_OK:
            raise EdsdkError(name, err)

    def call_raw(self, name, *args):
        return getattr(self.dll, name)(*args)

    # SDK lifetime
    def initialize(self):
        self._call("EdsInitializeSDK")

    def terminate(self):
        self.dll.EdsTerminateSDK()

    def release(self, ref):
        if ref:
            self.dll.EdsRelease(ref)

    # Cameras
    def first_camera(self):
        cam_list = EdsBaseRef()
        self._call("EdsGetCameraList", byref(cam_list))
        try:
            count = c_int32()
            self._call("EdsGetChildCount", cam_list, byref(count))
            if count.value == 0:
                return None
            cam = EdsBaseRef()
            self._call("EdsGetChildAtIndex", cam_list, 0, byref(cam))
            return cam
        finally:
            self.release(cam_list)

    def device_description(self, cam):
        info = EdsDeviceInfo()
        self._call("EdsGetDeviceInfo", cam, byref(info))
        return info.szDeviceDescription.decode("utf-8", "replace")

    def open_session(self, cam):
        self._call("EdsOpenSession", cam)

    def close_session(self, cam):
        self.dll.EdsCloseSession(cam)

    # Properties
    def get_uint32(self, ref, prop_id):
        value = c_uint32()
        self._call("EdsGetPropertyData", ref, prop_id, 0, 4, byref(value))
        return value.value

    def set_uint32(self, ref, prop_id, value):
        data = c_uint32(value & 0xFFFFFFFF)
        self._call("EdsSetPropertyData", ref, prop_id, 0, 4, byref(data))

    def get_string(self, ref, prop_id):
        data_type, size = c_uint32(), c_uint32()
        self._call("EdsGetPropertySize", ref, prop_id, 0, byref(data_type), byref(size))
        buf = ctypes.create_string_buffer(max(size.value, 1))
        self._call("EdsGetPropertyData", ref, prop_id, 0, size.value, buf)
        return buf.value.decode("utf-8", "replace")

    def get_desc(self, ref, prop_id):
        desc = EdsPropertyDesc()
        self._call("EdsGetPropertyDesc", ref, prop_id, byref(desc))
        return [desc.propDesc[i] & 0xFFFFFFFF for i in range(desc.numElements)]

    def send_command(self, cam, command, param=0):
        self._call("EdsSendCommand", cam, command, param)

    def set_capacity(self, cam):
        cap = EdsCapacity(0x7FFFFFFF, 0x1000, 1)
        self._call("EdsSetCapacity", cam, cap)

    # Handlers
    def set_object_handler(self, cam, handler):
        self._call("EdsSetObjectEventHandler", cam, kEdsObjectEvent_All, handler, None)

    def set_property_handler(self, cam, handler):
        self._call("EdsSetPropertyEventHandler", cam, kEdsPropertyEvent_All, handler, None)

    def set_state_handler(self, cam, handler):
        self._call("EdsSetCameraStateEventHandler", cam, kEdsStateEvent_All, handler, None)

    def set_camera_added_handler(self, handler):
        self._call("EdsSetCameraAddedHandler", handler, None)

    # Transfers
    def directory_item_info(self, item):
        """Return (size, filename).

        EDSDK 13.x uses a 64-bit size field while 3.x uses 32-bit, which
        shifts the filename by 4 bytes. Read raw bytes and detect the layout.
        """
        raw = (ctypes.c_ubyte * 320)()
        self._call("EdsGetDirectoryItemInfo", item, raw)
        data = bytes(raw)

        def name_at(offset):
            chunk = data[offset:offset + 256].split(b"\0", 1)[0]
            try:
                text = chunk.decode("ascii")
            except UnicodeDecodeError:
                return None
            return text if text and "." in text and text.isprintable() else None

        name = name_at(20)
        if name:
            size = int.from_bytes(data[0:8], "little")
        else:
            name = name_at(16) or "IMG.JPG"
            size = int.from_bytes(data[0:4], "little")
        return size, name

    def download(self, item, size, path):
        stream = EdsBaseRef()
        self._call("EdsCreateFileStream", path.encode("mbcs"),
                   kEdsFileCreateDisposition_CreateAlways, kEdsAccess_ReadWrite,
                   byref(stream))
        try:
            self._call("EdsDownload", item, c_uint64(size), stream)
            self._call("EdsDownloadComplete", item)
        finally:
            self.release(stream)

    # Live view
    def create_evf(self):
        stream = EdsBaseRef()
        self._call("EdsCreateMemoryStream", c_uint64(0), byref(stream))
        evf = EdsBaseRef()
        try:
            self._call("EdsCreateEvfImageRef", stream, byref(evf))
        except EdsdkError:
            self.release(stream)
            raise
        return stream, evf

    def download_evf(self, cam, stream, evf):
        """Return JPEG bytes of the current live view frame, or None if not ready."""
        err = self.dll.EdsDownloadEvfImage(cam, evf)
        if err == EDS_ERR_OBJECT_NOTREADY or err == EDS_ERR_DEVICE_BUSY:
            return None
        if err != EDS_ERR_OK:
            raise EdsdkError("EdsDownloadEvfImage", err)
        length = c_uint64(0)
        self._call("EdsGetLength", stream, byref(length))
        ptr = c_void_p()
        self._call("EdsGetPointer", stream, byref(ptr))
        if not ptr.value or not length.value:
            return None
        return ctypes.string_at(ptr.value, length.value)
