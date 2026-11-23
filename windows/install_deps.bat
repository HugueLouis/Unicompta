@echo off
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>&1 || (
    echo Python not found. Install Python 3.12 from https://www.python.org/downloads/
    echo Tick "Add python.exe to PATH" and keep "tcl/tk and IDLE" selected.
    pause
    exit /b 1
)

if not exist venv\Scripts\python.exe (
    echo Creating virtual environment...
    python -m venv venv || (echo Could not create the venv & pause & exit /b 1)
)

call venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install lxml Pillow pymupdf copykitten matplotlib ollama pyinstaller
if errorlevel 1 (
    echo.
    echo FAILED: a package did not install, see the messages above.
    pause
    exit /b 1
)

echo.
echo All Python dependencies are installed in .\venv
echo.
echo OPTIONAL, for the PDF auto-fill suggestions:
echo   winget install Ollama.Ollama
echo   ollama pull gemma3:4b
echo.
pause
