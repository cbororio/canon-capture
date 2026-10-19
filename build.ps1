# Builds dist\CanonCapture.exe
# If an EDSDK folder (with EDSDK.dll + EdsImage.dll) exists next to this script,
# it is bundled into the exe. Otherwise put the DLLs next to the exe afterwards.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python make_icon.py
$args = @("--noconfirm", "--clean", "--onefile", "--windowed", "--name", "CanonCapture",
          "--icon", "CanonCapture.ico",
          "--exclude-module", "tkinter",
          "--exclude-module", "PySide6.QtNetwork", "--exclude-module", "PySide6.QtQml",
          "--exclude-module", "PySide6.QtQuick", "--exclude-module", "PySide6.QtPdf")
if (Test-Path "EDSDK\EDSDK.dll") { $args += @("--add-data", "EDSDK;EDSDK") }
python -m PyInstaller @args run.py
Write-Host "Built dist\CanonCapture.exe"
