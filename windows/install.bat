@echo off
chcp 65001 >nul
where git >nul 2>&1 || (
    echo Git is missing, installing it with winget...
    winget install --id Git.Git -e --silent
    echo.
    echo If this succeeded, close this window and run install.bat again.
    pause & exit /b
)
call "%~dp0setup_git.bat" /install

set "DATA=%LOCALAPPDATA%\Unicompta\UPSecretrariat"
if not exist "%DATA%\.git" (
    echo Downloading the accounting data, this can take a few minutes...
    git clone https://github.com/Tresorerie-UP/UPSecretrariat.git "%DATA%" || (
        echo CLONE FAILED: check the token and its permissions
        pause & exit /b 1
    )
)
> "%~dp0config" echo %DATA%\
>> "%~dp0config" echo %USERPROFILE%\Downloads\
echo Installation complete. Run Unicompta.exe
pause