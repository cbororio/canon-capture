Canon Capture
=============

Tethered photo capture for the Canon EOS 90D (and other EDSDK cameras) over USB.

Features
- Live view, autofocus, and shutter release from the PC
- ISO, aperture, shutter speed, exposure compensation and white balance controls
- Photos go straight to a folder you choose (optional copy kept on the SD card)
- Optional file name prefix: Prefix_YYYYMMDD_HHMMSS.JPG
- Filmstrip of recent photos (double-click to open, right-click for "Show in Folder")
- Keyboard: Space = shoot, F = focus, L = live view, G = grid, Ctrl+O = choose folder
- Follows the Windows light/dark setting

Canon SDK (required, one time)
Canon does not allow redistributing its SDK, so you need to get it yourself:
1. Sign up for the Canon developer programme (https://developercommunity.usa.canon.com,
   or the Canon developer site for your region) and download EDSDK for Windows.
2. From the EDSDK_64\Dll folder, copy EDSDK.dll and EdsImage.dll next to CanonCapture.exe
   (or into a folder named EDSDK next to it).

Camera setup
- Connect the camera with a USB cable and switch it on.
- Close EOS Utility; only one app can control the camera at a time.
- Set the camera's Wi-Fi/Bluetooth to Disable. The 90D will not accept USB control
  while wireless is on.
- Set auto power off to Disable for long sessions.

Building from source
  pip install PySide6-Essentials pyinstaller pillow
  powershell -ExecutionPolicy Bypass -File build.ps1
  Output: dist\CanonCapture.exe
To bundle the SDK inside the exe, create an EDSDK folder next to build.ps1 and put
the two DLLs in it before building.
