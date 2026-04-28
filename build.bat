@echo off
setlocal

echo ================================
echo Building DeliveryNoteParser.exe
echo ================================

REM 清理旧文件
rmdir /s /q build dist __pycache__ 2>nul
del *.spec 2>nul

REM 打包
pyinstaller ^
  --clean ^
  --onefile ^
  --name htm_parser ^
  htm_parser.py

echo.
echo ================================
echo Build finished
echo Output: dist\htm_parser.exe
echo ================================

pause