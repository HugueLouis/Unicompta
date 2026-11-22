@echo off
chcp 65001 >nul
where git >nul 2>&1 || (echo Install Git for Windows first: https://git-scm.com/download/win & pause & exit /b)
set "DATA=%LOCALAPPDATA%\Unicompta\UPSecretrariat"
if not exist "%DATA%" (
    echo Downloading the accounting data, this can take a few minutes...
    git clone https://github.com/Tresorerie-UP/UPSecretrariat.git "%DATA%"
)
> "%~dp0config" echo %DATA%\
>> "%~dp0config" echo %USERPROFILE%\Downloads\
call "%~dp0setup_git.bat"
echo Installation complete. Run Unicompta.exe
pause