@echo off
setlocal
cd /d "%~dp0.."
if not defined VOXNOTE_PYTHON set "VOXNOTE_PYTHON=%CD%\.venv\Scripts\python.exe"
set "PYTHON=%VOXNOTE_PYTHON%"

if not exist "%PYTHON%" (
  echo 找不到 Python 环境：%PYTHON%
  echo 请设置 VOXNOTE_PYTHON 指向 GPU Python。
  pause
  exit /b 1
)

"%PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
endlocal
