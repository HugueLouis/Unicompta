@echo off
set /p NAME=Full name: 
echo.
echo A GitHub page will open so you can create a token:
echo   - Repository access: Only select repositories, then pick the data repository
echo   - Permissions: Contents = Read and write
echo   - Expiration: 1 year
echo Click Generate token, copy it, then come back here.
start https://github.com/settings/personal-access-tokens/new
set /p TOKEN=Paste the token here: 
git config --global user.name "%NAME%"
git config --global user.email "unicompta@users.noreply.github.com"
(echo protocol=https& echo host=github.com& echo username=unicompta& echo password=%TOKEN%& echo.) | git credential approve
if "%~1"=="/install" exit /b

rem The repo folder can now be chosen inside the app, so the config file may not exist yet.
if not exist "%~dp0config" (
    echo Token saved. Start Unicompta.exe, pick the repository folder, then press Push to test the connection.
    pause
    exit /b
)
set /p BASE=<"%~dp0config"
cd /d "%BASE%"
git ls-remote origin >nul 2>&1 && (echo OK: GitHub connection successful) || (echo FAILED: check the token and its permissions on the repository)
pause