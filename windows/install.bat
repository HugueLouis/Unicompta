@echo off
wsl --status >nul 2>&1 || (wsl --install --no-distribution & echo Restart the PC, then run install.bat again & pause & exit /b)
wsl --import Unicompta "%LOCALAPPDATA%\Unicompta" "%~dp0Unicompta.tar"
echo Downloading the accounting data, this can take a few minutes...
wsl -d Unicompta -- git clone https://github.com/Tresorerie-UP/UPSecretrariat.git /data/UPSecretrariat
for /f "delims=" %%i in ('wsl -d Unicompta wslpath -u "%USERPROFILE:\=/%/Downloads"') do set DL=%%i
wsl -d Unicompta -- bash -c "printf '/data/UPSecretrariat/\n%%s/\n' '%DL%' > /Unicompta/config"
call "%~dp0setup_git.bat"
echo Installation complete. Use run.bat to start Unicompta.
pause