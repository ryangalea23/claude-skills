@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0record-call.ps1" %*
