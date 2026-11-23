@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist venv\Scripts\activate.bat (
    echo Run install_deps.bat first.
    pause
    exit /b 1
)
call venv\Scripts\activate.bat

pyinstaller --noconfirm --clean --onefile --windowed --name Unicompta ^
  --paths . ^
  --hidden-import matplotlib.backends.backend_tkagg ^
  --hidden-import lib.ML ^
  main.py
if errorlevel 1 (
    echo.
    echo BUILD FAILED, see the messages above.
    pause
    exit /b 1
)

REM install.bat creates the "config" file next to the exe and clones the data repo
copy /y install.bat dist\ >nul
copy /y setup_git.bat dist\ >nul

echo.
echo Done: dist\Unicompta.exe  (+ install.bat and setup_git.bat to ship with it)
pause