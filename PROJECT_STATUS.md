# Canon Capture – project status

_Last updated: 2026-10-07_

## What it is
Windows desktop app (single `.exe`) for tethered **photo** capture with a Canon EOS 90D over USB.
Video recording is out of scope for now. The UI is styled after macOS apps: traffic-light window
buttons, a grouped sidebar, toggle switches, and light/dark mode that follows Windows.

## Done
- App source in `canon_capture\`:
  - `edsdk.py`: ctypes bindings for Canon EDSDK
  - `camera.py`: session, live view, capture, autofocus, property sync, downloads to the PC
  - `app.py`: main window
  - `widgets.py`: Mac-style widgets
  - `chrome.py`: frameless window with native snap and resize
  - `props.py`: value labels for ISO, aperture, shutter speed, exposure compensation and white balance
- Built exe: `dist\CanonCapture.exe`. It launches and the UI works; it has not been tested with a camera.
- Build: `powershell -ExecutionPolicy Bypass -File build.ps1` (needs PySide6-Essentials,
  pyinstaller >= 6.22 and pillow; PyInstaller 6.10 crashes with PySide6 6.11).

## Waiting on
- Canon EDSDK access. The account is registered at https://developers.canon-europe.com, EDSDK access
  has been requested, and the profile description has been filled in. Canon is reviewing the request.

## Next steps (once Canon approves)
1. Log in and download **EDSDK for Windows** (latest version).
2. Copy `EDSDK_64\Dll\EDSDK.dll` and `EdsImage.dll` into `dist\` next to the exe
   (or into an `EDSDK\` folder here, then rebuild so they are bundled inside the exe).
3. Camera: Wi-Fi/Bluetooth **off**, EOS Utility closed, USB connected, camera on.
4. Test: live view, focus, shutter, each exposure dropdown, the "Keep copy on SD card" switch,
   folder choice and the name prefix, and RAW+JPEG downloads.
5. Things to check during testing:
   - The `directory_item_info` layout detection in `edsdk.py` (it handles both SDK 3.x and 13.x structs).
   - That saving to the PC works without an SD card in the camera.
